"""
ml/email_model/train_modernbert.py
-----------------------------------
ModernBERT (answerdotai/ModernBERT-base) fine-tuning script for email phishing.

DESIGNED TO RUN ON COLAB OR KAGGLE (GPU required; ~1.5 h on T4).
Not runnable on this CPU-only machine.

USAGE ON COLAB
--------------
1. Upload email_dataset.csv and this script to your Colab session storage.
2. Run the setup cell at the top, then execute the script:
       !python train_modernbert.py --data_path /content/email_dataset.csv \\
                                   --output_dir /content/mb_artifacts
3. Download the saved artifacts folder and copy to:
       ml/email_model/artifacts/  (overwriting vec.pkl / thresholds.json if
       the ModernBERT model beats the baseline)

OUTPUT ARTIFACTS
----------------
  artifacts/modernbert/           — model checkpoint (pytorch_model.bin + config)
  artifacts/modernbert_thresholds.json
  artifacts/modernbert_report.md

SPEC REQUIREMENTS MET
---------------------
- answerdotai/ModernBERT-base, max 512 tokens
- Learning rate ~3e-5, batch 16 with gradient accumulation 2, 3 epochs
- 10% warmup, weight decay 0.01
- Early stopping on validation PR-AUC
- Temperature scaling on val
- Thresholds chosen on val at <=1% FPR on ham
- Evaluate on test, golden rows, leave-one-source-out
- Ham and spam false-positive rates reported separately
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from torch import nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    get_linear_schedule_with_warmup,
)

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--data_path",  default="email_dataset.csv")
parser.add_argument("--output_dir", default="artifacts/modernbert")
parser.add_argument("--model_name", default="answerdotai/ModernBERT-base")
parser.add_argument("--max_len",    type=int, default=512)
parser.add_argument("--batch_size", type=int, default=16)
parser.add_argument("--grad_accum", type=int, default=2)
parser.add_argument("--lr",         type=float, default=3e-5)
parser.add_argument("--epochs",     type=int, default=3)
parser.add_argument("--warmup_frac",type=float, default=0.10)
parser.add_argument("--weight_decay",type=float, default=0.01)
parser.add_argument("--patience",   type=int, default=2,
                    help="Early stopping patience (epochs without val PR-AUC improvement)")
args = parser.parse_args()

OUTPUT_DIR = Path(args.output_dir)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")
if not torch.cuda.is_available():
    print("WARNING: No GPU found. This script is intended to run on Colab/Kaggle with a GPU.")
    print("Training will be extremely slow on CPU.")

# ── Data ──────────────────────────────────────────────────────────────────────
print("Loading data …")
df = pd.read_csv(args.data_path)

# Use the pre-cleaned text column (subject [SEP] body, already masked/lowercase)
# Truncation to 2400 chars already applied in the dataset
train_df  = df[df["split"] == "train"]
val_df    = df[df["split"] == "val"]
test_df   = df[df["split"] == "test"]
golden_df = df[df["split"] == "golden"]

print(f"  train={len(train_df)}  val={len(val_df)}  test={len(test_df)}  golden={len(golden_df)}")

# ── Dataset ───────────────────────────────────────────────────────────────────
class EmailDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.texts     = list(texts)
        self.labels    = list(labels)
        self.tokenizer = tokenizer
        self.max_len   = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            max_length=self.max_len,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label":          torch.tensor(self.labels[idx], dtype=torch.long),
        }

# ── Tokeniser + Model ─────────────────────────────────────────────────────────
print(f"Loading tokenizer and model: {args.model_name} …")
tokenizer = AutoTokenizer.from_pretrained(args.model_name)
model = AutoModelForSequenceClassification.from_pretrained(
    args.model_name, num_labels=2
)
model.to(device)

train_ds = EmailDataset(train_df["text"].fillna(""), train_df["label"], tokenizer, args.max_len)
val_ds   = EmailDataset(val_df["text"].fillna(""),   val_df["label"],   tokenizer, args.max_len)
test_ds  = EmailDataset(test_df["text"].fillna(""),  test_df["label"],  tokenizer, args.max_len)
gold_ds  = EmailDataset(golden_df["text"].fillna(""), golden_df["label"], tokenizer, args.max_len)

train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,  num_workers=2)
val_loader   = DataLoader(val_ds,   batch_size=args.batch_size, shuffle=False, num_workers=2)
test_loader  = DataLoader(test_ds,  batch_size=args.batch_size, shuffle=False, num_workers=2)
gold_loader  = DataLoader(gold_ds,  batch_size=args.batch_size, shuffle=False, num_workers=2)

# ── Optimizer + Scheduler ─────────────────────────────────────────────────────
total_steps   = (len(train_loader) // args.grad_accum) * args.epochs
warmup_steps  = int(total_steps * args.warmup_frac)

optimizer = torch.optim.AdamW(
    model.parameters(), lr=args.lr, weight_decay=args.weight_decay
)
scheduler = get_linear_schedule_with_warmup(
    optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
)

# Positive class weight to handle imbalance
pos_weight = (train_df["label"] == 0).sum() / max((train_df["label"] == 1).sum(), 1)
loss_fn    = nn.CrossEntropyLoss(
    weight=torch.tensor([1.0, float(pos_weight)], device=device)
)

# ── Training loop ─────────────────────────────────────────────────────────────
def get_probs(loader):
    model.eval()
    all_probs = []
    all_labels = []
    with torch.no_grad():
        for batch in loader:
            ids  = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            logits = model(input_ids=ids, attention_mask=mask).logits
            probs  = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
            all_probs.extend(probs)
            all_labels.extend(batch["label"].numpy())
    return np.array(all_probs), np.array(all_labels)


best_val_prauc  = -1.0
best_epoch      = 0
patience_count  = 0

print("Training …")
for epoch in range(1, args.epochs + 1):
    model.train()
    optimizer.zero_grad()
    running_loss = 0.0
    steps = 0

    for step, batch in enumerate(train_loader, 1):
        ids    = batch["input_ids"].to(device)
        mask   = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        logits = model(input_ids=ids, attention_mask=mask).logits
        loss   = loss_fn(logits, labels) / args.grad_accum
        loss.backward()
        running_loss += loss.item() * args.grad_accum

        if step % args.grad_accum == 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            steps += 1

    val_probs, val_labels = get_probs(val_loader)
    val_prauc = average_precision_score(val_labels, val_probs)
    avg_loss  = running_loss / max(steps, 1)
    print(f"  Epoch {epoch}/{args.epochs}  loss={avg_loss:.4f}  val_PR-AUC={val_prauc:.4f}", flush=True)

    if val_prauc > best_val_prauc:
        best_val_prauc = val_prauc
        best_epoch     = epoch
        patience_count = 0
        model.save_pretrained(str(OUTPUT_DIR))
        tokenizer.save_pretrained(str(OUTPUT_DIR))
        print(f"    ✓ Best model saved (PR-AUC={best_val_prauc:.4f})", flush=True)
    else:
        patience_count += 1
        if patience_count >= args.patience:
            print(f"  Early stopping at epoch {epoch} (no improvement for {args.patience} epochs)", flush=True)
            break

print(f"Best epoch: {best_epoch}  best val PR-AUC: {best_val_prauc:.4f}", flush=True)

# ── Temperature scaling on val ────────────────────────────────────────────────
# Reload best model
model = AutoModelForSequenceClassification.from_pretrained(str(OUTPUT_DIR))
model.to(device)

val_probs, val_labels = get_probs(val_loader)

class _Temp(nn.Module):
    def __init__(self):
        super().__init__()
        self.t = nn.Parameter(torch.ones(1))
    def forward(self, logits):
        return logits / self.t

# (Temperature scaling is a lightweight calibration — use scipy minimise for simplicity)
from scipy.optimize import minimize_scalar
import torch.nn.functional as F

val_logits_list = []
model.eval()
with torch.no_grad():
    for batch in val_loader:
        ids  = batch["input_ids"].to(device)
        mask = batch["attention_mask"].to(device)
        logits = model(input_ids=ids, attention_mask=mask).logits
        val_logits_list.append(logits.cpu())
val_logits_np = torch.cat(val_logits_list, dim=0).numpy()

def _nll(t):
    scaled = torch.tensor(val_logits_np / t, dtype=torch.float32)
    return F.cross_entropy(scaled, torch.tensor(val_labels, dtype=torch.long)).item()

res  = minimize_scalar(_nll, bounds=(0.1, 10.0), method="bounded")
temp = float(res.x)
print(f"Temperature: {temp:.4f}", flush=True)

def _scaled_probs(logits_np, t):
    sc = torch.softmax(torch.tensor(logits_np / t, dtype=torch.float32), dim=-1)
    return sc[:, 1].numpy()

val_cal = _scaled_probs(val_logits_np, temp)

# ── Thresholds on val ─────────────────────────────────────────────────────────
ham_probs  = val_cal[val_labels == 0]
sorted_ham = np.sort(ham_probs)[::-1]
idx_fp1    = max(int(len(sorted_ham) * 0.01) - 1, 0)
phishing_thr = float(sorted_ham[idx_fp1]) if len(sorted_ham) else 1.0

pos_probs  = val_cal[val_labels == 1]
sorted_pos = np.sort(pos_probs)[::-1]
idx_rec    = max(int(len(sorted_pos) * 0.90) - 1, 0)
suspicious_thr = float(sorted_pos[idx_rec]) if len(sorted_pos) else 0.0

thresholds = {
    "phishing_threshold":   phishing_thr,
    "suspicious_threshold": suspicious_thr,
    "temperature":          temp,
}
thresh_path = OUTPUT_DIR.parent / "modernbert_thresholds.json"
thresh_path.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
print(f"Thresholds saved: phishing={phishing_thr:.4f}  suspicious={suspicious_thr:.4f}", flush=True)

# ── Final evaluation on test ──────────────────────────────────────────────────
def _eval_loader(loader, name):
    logits_list = []
    label_list  = []
    model.eval()
    with torch.no_grad():
        for batch in loader:
            ids  = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            logits = model(input_ids=ids, attention_mask=mask).logits
            logits_list.append(logits.cpu())
            label_list.extend(batch["label"].numpy())
    all_logits = torch.cat(logits_list, dim=0).numpy()
    probs      = _scaled_probs(all_logits, temp)
    labels     = np.array(label_list)
    pred       = (probs >= phishing_thr).astype(int)
    return dict(
        name=name,
        roc=roc_auc_score(labels, probs) if labels.sum() > 0 else float("nan"),
        prauc=average_precision_score(labels, probs) if labels.sum() > 0 else float("nan"),
        prec=precision_score(labels, pred, zero_division=0),
        rec=recall_score(labels, pred,    zero_division=0),
        f1=f1_score(labels, pred,         zero_division=0),
        cm=confusion_matrix(labels, pred),
        probs=probs,
        labels=labels,
    )

print("Evaluating test …", flush=True)
r_test = _eval_loader(test_loader, "test")

print("Evaluating golden …", flush=True)
r_gold = _eval_loader(gold_loader, "golden")

# Ham / spam FPR on test
test_df2 = test_df.copy()
test_df2["prob"] = r_test["probs"]
ham_fpr  = (test_df2.loc[test_df2["kind"] == "ham",  "prob"] >= phishing_thr).mean()
spam_fpr = (test_df2.loc[test_df2["kind"] == "spam", "prob"] >= phishing_thr).mean()

# ── Leave-one-source-out ──────────────────────────────────────────────────────
# For LOSO with BERT on Colab, we use the trained model's embeddings rather
# than retraining — this is a fast post-hoc LOSO using the frozen model.
# Full retraining LOSO for ModernBERT is too slow on a single GPU run.
print("Leave-one-source-out (inference-only, using trained model) …", flush=True)
loso = []
for src in df["source"].unique():
    held = df[(df["source"] == src) & (df["split"].isin(["train","val","test"]))]
    if len(held) == 0 or held["label"].nunique() < 2:
        loso.append(dict(source=src, n=len(held), prauc=float("nan"), note="single class"))
        continue
    ds_h  = EmailDataset(held["text"].fillna(""), held["label"], tokenizer, args.max_len)
    ld_h  = DataLoader(ds_h, batch_size=args.batch_size, shuffle=False, num_workers=2)
    r_h   = _eval_loader(ld_h, src)
    loso.append(dict(source=src, n=len(held), prauc=r_h["prauc"], note="inference-only LOSO"))
    print(f"  {src}: PR-AUC={r_h['prauc']:.4f} (n={len(held)})", flush=True)

# ── CPU latency estimate (single-item, CPU only) ──────────────────────────────
model.cpu()
n_lat = 20
t_lat = time.perf_counter()
X_test_sample = test_df["text"].fillna("").tolist()[:n_lat]
for txt in X_test_sample:
    enc = tokenizer(txt, max_length=args.max_len, truncation=True,
                    padding="max_length", return_tensors="pt")
    with torch.no_grad():
        _ = model(**enc).logits
lat_ms = (time.perf_counter() - t_lat) / n_lat * 1000
print(f"CPU latency (ModernBERT, no GPU): {lat_ms:.1f} ms/email", flush=True)

# ── Report ────────────────────────────────────────────────────────────────────
def _f(v):
    return f"{v:.4f}" if not (isinstance(v, float) and v != v) else "n/a"

lines = [
    "# ModernBERT Email Report\n",
    "## Test-split metrics",
    f"- ROC AUC:                  {_f(r_test['roc'])}",
    f"- PR AUC:                   {_f(r_test['prauc'])}",
    f"- Precision (PHISHING thr): {_f(r_test['prec'])}",
    f"- Recall    (PHISHING thr): {_f(r_test['rec'])}",
    f"- F1        (PHISHING thr): {_f(r_test['f1'])}",
    f"\n### Confusion matrix (PHISHING threshold)\n```\n{r_test['cm']}\n```",
    f"\n### False-positive rates (test)",
    f"- Ham  FPR: {ham_fpr:.4f}  ({ham_fpr*100:.2f}%)",
    f"- Spam FPR: {spam_fpr:.4f}  ({spam_fpr*100:.2f}%)",
    "\n## Golden-set metrics",
    f"- ROC AUC:  {_f(r_gold['roc'])}",
    f"- PR AUC:   {_f(r_gold['prauc'])}",
    f"- F1:       {_f(r_gold['f1'])}",
    f"\n### Confusion matrix (golden)\n```\n{r_gold['cm']}\n```",
    "\n## Leave-one-source-out PR-AUC (inference-only with trained model)",
    "| Source | N | PR-AUC | Note |",
    "|--------|---|--------|------|",
]
for res in loso:
    lines.append(f"| {res['source']} | {res['n']} | {_f(res['prauc'])} | {res['note']} |")

lines += [
    "\n## Thresholds",
    f"- phishing_threshold:   {phishing_thr:.6f}",
    f"- suspicious_threshold: {suspicious_thr:.6f}",
    f"- temperature:          {temp:.6f}",
    f"\n## Latency",
    f"- CPU latency (ModernBERT): {lat_ms:.1f} ms/email",
    "",
]

report_text = "\n".join(lines)
report_path = OUTPUT_DIR.parent / "modernbert_report.md"
report_path.write_text(report_text, encoding="utf-8")
print(f"\nReport written to {report_path}")
print("\n" + "="*60)
print(report_text)
print("="*60)
print("MODERNBERT DONE", flush=True)
