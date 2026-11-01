"""Memory-conscious ModernBERT fine-tuning for the email phishing task."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import nullcontext
from itertools import cycle
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch import nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ml.shared.config import DATA_DIR


parser = argparse.ArgumentParser()
parser.add_argument("--data_path", default=str(Path(DATA_DIR) / "email_dataset.csv"))
parser.add_argument("--output_dir", default="ml/email_model/artifacts/modernbert")
parser.add_argument("--checkpoint_dir", default=None,
                    help="Checkpoint directory; defaults to the legacy shared location")
parser.add_argument("--model_name", default="answerdotai/ModernBERT-base")
parser.add_argument("--max_len", type=int, default=256)
parser.add_argument("--batch_size", type=int, default=4)
parser.add_argument("--grad_accum", type=int, default=8)
parser.add_argument("--lr", type=float, default=3e-5)
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--warmup_frac", type=float, default=0.10)
parser.add_argument("--weight_decay", type=float, default=0.01)
parser.add_argument("--patience", type=int, default=2)
parser.add_argument("--online", action="store_true",
                    help="Allow Hugging Face network access instead of offline cache-only loading")
parser.add_argument("--resume", action="store_true",
                    help="Resume from the newest checkpoint in the checkpoint directory")
parser.add_argument("--max_minutes", type=float, default=0.0,
                    help="Stop after this many minutes and save a checkpoint; zero means unlimited")
parser.add_argument("--smoke", action="store_true",
                    help="Run 20 optimizer steps on 200 random training rows without saving checkpoints")
parser.add_argument("--holdout_path", default=None,
                    help="Optional cleaned CSV with text and label columns for separate evaluation")
args = parser.parse_args()

if args.online:
    os.environ.pop("HF_HUB_OFFLINE", None)

OUTPUT_DIR = Path(args.output_dir)
CHECKPOINT_DIR = (
    Path(args.checkpoint_dir)
    if args.checkpoint_dir
    else OUTPUT_DIR.parent / "ckpt"
)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
use_bf16 = device.type == "cuda"
loader_workers = 0


class EmailDataset(Dataset):
    def __init__(self, texts: pd.Series, labels: pd.Series):
        self.texts = texts.fillna("").tolist()
        self.labels = torch.as_tensor(labels.tolist(), dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> tuple[str, torch.Tensor]:
        return self.texts[index], self.labels[index]


def make_collate(tokenizer):
    def collate(batch):
        texts, labels = zip(*batch)
        encoded = tokenizer(
            list(texts),
            max_length=args.max_len,
            truncation=True,
            padding=True,
            return_tensors="pt",
        )
        encoded["labels"] = torch.stack(labels)
        return encoded

    return collate


def process_ram_gb() -> float | None:
    try:
        import psutil
    except ImportError:
        return None
    return psutil.Process().memory_info().rss / (1024**3)


def peak_gpu_gb() -> float:
    if device.type != "cuda":
        return 0.0
    return torch.cuda.max_memory_allocated() / (1024**3)


def autocast_context():
    if use_bf16:
        return torch.autocast("cuda", dtype=torch.bfloat16)
    return nullcontext()


def checkpoint_candidates() -> list[Path]:
    if not CHECKPOINT_DIR.exists():
        return []
    return sorted(
        (path for path in CHECKPOINT_DIR.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )


def load_model(model_name_or_path: str, load_kwargs: dict):
    model_kwargs = {
        "num_labels": 2,
        "attn_implementation": "sdpa",
        "reference_compile": False,
        **load_kwargs,
    }
    try:
        return AutoModelForSequenceClassification.from_pretrained(
            model_name_or_path, **model_kwargs
        )
    except TypeError as exc:
        if "reference_compile" not in str(exc):
            raise
        print(
            "WARNING: installed Transformers does not support reference_compile; "
            "retrying without it (torch.compile is never used).",
            flush=True,
        )
        model_kwargs.pop("reference_compile")
        return AutoModelForSequenceClassification.from_pretrained(
            model_name_or_path, **model_kwargs
        )


def save_checkpoint(model, tokenizer, optimizer, scheduler, epoch, optimizer_step):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"step-{optimizer_step:07d}"
    path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(path))
    tokenizer.save_pretrained(str(path))
    torch.save(
        {
            "epoch": epoch,
            "optimizer_step": optimizer_step,
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
        },
        path / "training_state.pt",
    )
    print(f"Checkpoint saved: {path}", flush=True)


def load_resume(model, optimizer, scheduler) -> tuple[int, int]:
    candidates = checkpoint_candidates()
    if not candidates:
        print("Resume requested, but no checkpoint was found; starting fresh.", flush=True)
        return 1, 0
    path = candidates[-1]
    state_path = path / "training_state.pt"
    if not state_path.exists():
        raise FileNotFoundError(f"Checkpoint state is missing: {state_path}")
    model_state = load_model(str(path), {"local_files_only": True})
    model.load_state_dict(model_state.state_dict())
    state = torch.load(state_path, map_location="cpu", weights_only=False)
    optimizer.load_state_dict(state["optimizer"])
    scheduler.load_state_dict(state["scheduler"])
    print(f"Resuming from checkpoint: {path}", flush=True)
    return int(state["epoch"]) + 1, int(state["optimizer_step"])


def evaluate_loader(model, loader, name, threshold=0.5):
    model.eval()
    probabilities = []
    labels = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            with autocast_context():
                logits = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                ).logits
            probabilities.extend(torch.softmax(logits.float(), dim=-1)[:, 1].cpu().numpy())
            labels.extend(batch["labels"].cpu().numpy())
    probabilities = np.asarray(probabilities)
    labels = np.asarray(labels)
    predictions = (probabilities >= threshold).astype(int)
    return {
        "name": name,
        "roc": roc_auc_score(labels, probabilities) if labels.sum() > 0 else float("nan"),
        "prauc": average_precision_score(labels, probabilities) if labels.sum() > 0 else float("nan"),
        "precision": precision_score(labels, predictions, zero_division=0),
        "recall": recall_score(labels, predictions, zero_division=0),
        "f1": f1_score(labels, predictions, zero_division=0),
        "cm": confusion_matrix(labels, predictions),
    }


def find_best_threshold(model, loader) -> tuple[float, float]:
    model.eval()
    probabilities = []
    labels = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            with autocast_context():
                logits = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                ).logits
            probabilities.extend(torch.softmax(logits.float(), dim=-1)[:, 1].cpu().numpy())
            labels.extend(batch["labels"].cpu().numpy())
    probabilities = np.asarray(probabilities)
    labels = np.asarray(labels)
    candidates = np.unique(np.concatenate(([0.5], probabilities)))
    scores = [
        f1_score(labels, (probabilities >= threshold).astype(int), zero_division=0)
        for threshold in candidates
    ]
    best_index = int(np.argmax(scores))
    return float(candidates[best_index]), float(scores[best_index])


def main() -> int:
    print(f"Device: {device}", flush=True)
    print(f"BF16 autocast: {use_bf16}", flush=True)
    print(f"Loading data: {args.data_path}", flush=True)
    df = pd.read_csv(args.data_path)
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]
    golden_df = df[df["split"] == "golden"]
    holdout_df = None
    if args.holdout_path:
        holdout_df = pd.read_csv(args.holdout_path)
        required_columns = {"text", "label"}
        missing = required_columns - set(holdout_df.columns)
        if missing:
            raise ValueError(
                f"Holdout CSV is missing required columns: {sorted(missing)}"
            )
        print(f"holdout={len(holdout_df)}", flush=True)

    if args.smoke:
        train_df = train_df.sample(n=min(200, len(train_df)), random_state=42)
        print(f"Smoke rows: {len(train_df)}", flush=True)
    print(
        f"train={len(train_df)} val={len(val_df)} "
        f"test={len(test_df)} golden={len(golden_df)}",
        flush=True,
    )

    load_kwargs = {"local_files_only": not args.online}
    print(f"Loading tokenizer and model: {args.model_name}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, **load_kwargs)
    model = load_model(args.model_name, load_kwargs)
    model.to(device)
    try:
        model.gradient_checkpointing_enable()
        print("Gradient checkpointing: enabled", flush=True)
    except (AttributeError, NotImplementedError, ValueError) as exc:
        print(f"WARNING: gradient checkpointing unsupported: {exc}", flush=True)

    collate_fn = make_collate(tokenizer)
    train_ds = EmailDataset(train_df["text"], train_df["label"])
    val_ds = EmailDataset(val_df["text"], val_df["label"])
    test_ds = EmailDataset(test_df["text"], test_df["label"])
    golden_ds = EmailDataset(golden_df["text"], golden_df["label"])
    holdout_ds = (
        EmailDataset(holdout_df["text"], holdout_df["label"])
        if holdout_df is not None
        else None
    )
    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=loader_workers, collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=loader_workers, collate_fn=collate_fn,
    )
    test_loader = DataLoader(
        test_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=loader_workers, collate_fn=collate_fn,
    )
    golden_loader = DataLoader(
        golden_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=loader_workers, collate_fn=collate_fn,
    )
    holdout_loader = (
        DataLoader(
            holdout_ds, batch_size=args.batch_size, shuffle=False,
            num_workers=loader_workers, collate_fn=collate_fn,
        )
        if holdout_ds is not None
        else None
    )

    counts = np.bincount(train_df["label"].to_numpy(), minlength=2).astype(float)
    class_weights = counts.sum() / np.maximum(2.0 * counts, 1.0)
    print(f"Class weights: {class_weights.tolist()}", flush=True)
    loss_fn = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device)
    )
    steps_per_epoch = max(len(train_loader) // args.grad_accum, 1)
    total_steps = steps_per_epoch * args.epochs
    scheduler_steps = max(total_steps, 20 if args.smoke else total_steps)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(scheduler_steps * args.warmup_frac),
        num_training_steps=scheduler_steps,
    )
    start_epoch, optimizer_step = (1, 0)
    if args.resume and not args.smoke:
        start_epoch, optimizer_step = load_resume(model, optimizer, scheduler)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    model.train()
    start_time = time.perf_counter()
    peak_ram = process_ram_gb()
    max_optimizer_steps = 20 if args.smoke else None
    stopped_by_time = False
    stop_training = False
    for epoch in range(start_epoch, args.epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        running_loss = 0.0
        batches_in_epoch = 0
        batch_iterator = cycle(train_loader) if args.smoke else iter(train_loader)
        epoch_start = time.perf_counter()
        while True:
            if max_optimizer_steps is not None and optimizer_step >= max_optimizer_steps:
                stop_training = True
                break
            if args.max_minutes and (time.perf_counter() - start_time) >= args.max_minutes * 60:
                stopped_by_time = True
                stop_training = True
                break
            try:
                accumulation_batches = []
                for _ in range(args.grad_accum):
                    try:
                        accumulation_batches.append(next(batch_iterator))
                    except StopIteration:
                        stop_training = True
                        break
                if stop_training:
                    break
                for batch in accumulation_batches:
                    batch = {key: value.to(device) for key, value in batch.items()}
                    with autocast_context():
                        logits = model(
                            input_ids=batch["input_ids"],
                            attention_mask=batch["attention_mask"],
                        ).logits
                        loss = loss_fn(logits, batch["labels"]) / args.grad_accum
                    loss.backward()
                    running_loss += loss.item() * args.grad_accum
                    batches_in_epoch += 1
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                optimizer_step += 1
            except torch.cuda.OutOfMemoryError:
                print(
                    f"CUDA OOM: batch_size={args.batch_size}, max_len={args.max_len}",
                    flush=True,
                )
                return 1

            current_ram = process_ram_gb()
            if current_ram is not None:
                peak_ram = max(peak_ram or current_ram, current_ram)
            if optimizer_step % 10 == 0:
                elapsed = time.perf_counter() - epoch_start
                seconds_per_step = elapsed / max(optimizer_step % steps_per_epoch or steps_per_epoch, 1)
                completed = optimizer_step % steps_per_epoch or steps_per_epoch
                remaining = max(steps_per_epoch - completed, 0)
                eta = remaining * seconds_per_step
                ram_text = f"{current_ram:.2f}" if current_ram is not None else "not available"
                print(
                    f"step={optimizer_step} loss={running_loss / max(batches_in_epoch, 1):.4f} "
                    f"sec_per_step={seconds_per_step:.2f} "
                    f"gpu_peak_gb={peak_gpu_gb():.2f} ram_gb={ram_text} eta_sec={eta:.1f}",
                    flush=True,
                )
            if optimizer_step % 500 == 0 and not args.smoke:
                save_checkpoint(model, tokenizer, optimizer, scheduler, epoch, optimizer_step)
            if max_optimizer_steps is not None and optimizer_step >= max_optimizer_steps:
                stop_training = True
                break
        if stop_training:
            if not args.smoke:
                save_checkpoint(model, tokenizer, optimizer, scheduler, epoch, optimizer_step)
            break
        if not args.smoke:
            save_checkpoint(model, tokenizer, optimizer, scheduler, epoch, optimizer_step)
        val_result = evaluate_loader(model, val_loader, "val")
        print(f"Epoch {epoch}: val_PR-AUC={val_result['prauc']:.4f}", flush=True)

    elapsed = time.perf_counter() - start_time
    if args.smoke:
        seconds_per_step = elapsed / max(optimizer_step, 1)
        full_epoch_steps = len(df[df["split"] == "train"]) / (args.batch_size * args.grad_accum)
        print(f"Smoke seconds per step: {seconds_per_step:.2f}", flush=True)
        print(f"Smoke peak GPU GB: {peak_gpu_gb():.2f}", flush=True)
        print(
            f"Smoke peak RAM GB: {peak_ram:.2f}" if peak_ram is not None
            else "Smoke peak RAM GB: not available",
            flush=True,
        )
        print(
            f"Smoke extrapolated full epoch seconds: "
            f"{seconds_per_step * full_epoch_steps:.1f}",
            flush=True,
        )
        print("SMOKE DONE; no checkpoints saved", flush=True)
        return 0
    if stopped_by_time:
        print("Stopped gracefully at --max_minutes.", flush=True)
    threshold, val_f1 = find_best_threshold(model, val_loader)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "threshold.json").open("w", encoding="utf-8") as handle:
        json.dump({"threshold": threshold, "validation_f1": val_f1}, handle, indent=2)
    print(
        f"Validation-selected threshold: {threshold:.6f} "
        f"(val_F1={val_f1:.4f})",
        flush=True,
    )
    print("Final evaluation:", flush=True)
    print(
        json.dumps(evaluate_loader(model, test_loader, "test", threshold), default=str),
        flush=True,
    )
    print(
        json.dumps(evaluate_loader(model, golden_loader, "golden", threshold), default=str),
        flush=True,
    )
    if holdout_loader is not None:
        print(
            json.dumps(
                evaluate_loader(model, holdout_loader, "holdout", threshold),
                default=str,
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
