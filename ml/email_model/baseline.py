"""
ml/email_model/baseline.py
--------------------------
TF-IDF (hashing) + SGD / Logistic Regression email phishing baseline.
Uses HashingVectorizer so it runs inside the 2 GB RAM available on this machine.
Saves artifacts to ml/email_model/artifacts/.

Artifacts written:
  artifacts/vec.pkl              — fitted HashingVectorizer config (params only)
  artifacts/logreg.pkl           — fitted SGDClassifier
  artifacts/thresholds.json      — {phishing_threshold, suspicious_threshold}
  artifacts/baseline_report.md   — full metrics report

Usage (CPU, ~2 min):
    python ml/email_model/baseline.py
"""
from __future__ import annotations

import sys
import json
import time
import pickle
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
)

from ml.shared.config import DATA_DIR

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_PATH     = Path(DATA_DIR) / "email_dataset.csv"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

VEC_PATH    = ARTIFACTS_DIR / "vec.pkl"
CLF_PATH    = ARTIFACTS_DIR / "logreg.pkl"
THRESH_PATH = ARTIFACTS_DIR / "thresholds.json"
REPORT_PATH = Path(__file__).resolve().parent / "baseline_report.md"

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading email_dataset.csv …", flush=True)
df = pd.read_csv(DATA_PATH)

train_df  = df[df["split"] == "train"]
val_df    = df[df["split"] == "val"]
test_df   = df[df["split"] == "test"]
golden_df = df[df["split"] == "golden"]

X_train = train_df["text"].fillna("").tolist()
y_train = train_df["label"].values
X_val   = val_df["text"].fillna("").tolist()
y_val   = val_df["label"].values
X_test  = test_df["text"].fillna("").tolist()
y_test  = test_df["label"].values
X_gold  = golden_df["text"].fillna("").tolist()
y_gold  = golden_df["label"].values

print(f"  train={len(X_train)}  val={len(X_val)}  test={len(X_test)}  golden={len(X_gold)}", flush=True)

# ── Hashing vectorizer (memory-safe) ─────────────────────────────────────────
# 2^17 = 131072 features; unigrams+bigrams; l2 norm
print("Vectorising (HashingVectorizer, unigrams+bigrams, 2^17 features) …", flush=True)
vec = HashingVectorizer(
    n_features=2**17,
    ngram_range=(1, 2),
    alternate_sign=False,
    norm="l2",
    strip_accents="unicode",
    analyzer="word",
)
t0 = time.time()
Xtr = vec.transform(X_train)
Xvl = vec.transform(X_val)
Xts = vec.transform(X_test)
Xgd = vec.transform(X_gold)
print(f"  Vectorisation: {time.time()-t0:.1f}s  shape={Xtr.shape}", flush=True)

# ── SGD with modified Huber loss (gives predict_proba) + isotonic calibration ─
print("Training SGDClassifier + isotonic calibration …", flush=True)
base_clf = SGDClassifier(
    loss="modified_huber",
    max_iter=200,
    tol=1e-4,
    class_weight="balanced",
    random_state=42,
    n_jobs=1,
)
model = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)
t1 = time.time()
model.fit(Xtr, y_train)
train_time = time.time() - t1
print(f"  Training time: {train_time:.1f}s", flush=True)

# ── Thresholds on val ─────────────────────────────────────────────────────────
print("Computing thresholds on val …", flush=True)
val_probs = model.predict_proba(Xvl)[:, 1]

ham_probs  = val_probs[y_val == 0]
sorted_ham = np.sort(ham_probs)[::-1]
idx_fp1    = max(int(len(sorted_ham) * 0.01) - 1, 0)
phishing_thr = float(sorted_ham[idx_fp1]) if len(sorted_ham) else 1.0

pos_probs  = val_probs[y_val == 1]
sorted_pos = np.sort(pos_probs)[::-1]
idx_rec    = max(int(len(sorted_pos) * 0.90) - 1, 0)
suspicious_thr = float(sorted_pos[idx_rec]) if len(sorted_pos) else 0.0

thresholds = {
    "phishing_threshold":   phishing_thr,
    "suspicious_threshold": suspicious_thr,
}
print(f"  phishing_thr={phishing_thr:.4f}  suspicious_thr={suspicious_thr:.4f}", flush=True)

# ── Save artifacts ────────────────────────────────────────────────────────────
with open(VEC_PATH, "wb") as f:
    pickle.dump(vec, f)
with open(CLF_PATH, "wb") as f:
    pickle.dump(model, f)
with open(THRESH_PATH, "w", encoding="utf-8") as f:
    json.dump(thresholds, f, indent=2)
print(f"Artifacts saved to {ARTIFACTS_DIR}", flush=True)

# ── CPU latency ───────────────────────────────────────────────────────────────
n_lat = 200
t2 = time.perf_counter()
for txt in X_test[:n_lat]:
    v = vec.transform([txt])
    _ = model.predict_proba(v)
latency_ms = (time.perf_counter() - t2) / n_lat * 1000
print(f"CPU latency: {latency_ms:.2f} ms/email", flush=True)

# ── Evaluation helpers ────────────────────────────────────────────────────────
def _eval_split(name, X_sp, y_true):
    probs = model.predict_proba(X_sp)[:, 1]
    pred  = (probs >= phishing_thr).astype(int)
    roc   = roc_auc_score(y_true, probs)  if y_true.sum() > 0 else float("nan")
    prauc = average_precision_score(y_true, probs) if y_true.sum() > 0 else float("nan")
    prec  = precision_score(y_true, pred, zero_division=0)
    rec   = recall_score(y_true, pred,    zero_division=0)
    f1    = f1_score(y_true, pred,        zero_division=0)
    cm    = confusion_matrix(y_true, pred)
    return dict(name=name, roc=roc, prauc=prauc, prec=prec, rec=rec, f1=f1, cm=cm, probs=probs)

print("Evaluating test split …", flush=True)
r_test = _eval_split("test", Xts, y_test)

print("Evaluating golden set …", flush=True)
r_gold = _eval_split("golden", Xgd, y_gold)

# Ham / spam false-positive rates
test_df2 = test_df.copy()
test_df2["prob"] = r_test["probs"]
ham_fpr  = (test_df2.loc[test_df2["kind"] == "ham",  "prob"] >= phishing_thr).mean()
spam_fpr = (test_df2.loc[test_df2["kind"] == "spam", "prob"] >= phishing_thr).mean()

# ── Leave-one-source-out ──────────────────────────────────────────────────────
print("Leave-one-source-out …", flush=True)
loso: list[dict] = []
for src in df["source"].unique():
    held = df[(df["source"] == src) & (df["split"].isin(["train", "val", "test"]))]
    rest = df[(df["source"] != src) & (df["split"] == "train")]
    if held["label"].nunique() < 2 or len(rest) == 0:
        loso.append(dict(source=src, n=len(held), prauc=float("nan"), note="single class"))
        continue
    Xr = vec.transform(rest["text"].fillna("").tolist())
    yr = rest["label"].values
    Xh = vec.transform(held["text"].fillna("").tolist())
    yh = held["label"].values
    lr_tmp = SGDClassifier(loss="modified_huber", max_iter=200, class_weight="balanced",
                           random_state=42, n_jobs=1)
    lr_tmp.fit(Xr, yr)
    ph = lr_tmp.predict_proba(Xh)[:, 1]
    pa = average_precision_score(yh, ph)
    loso.append(dict(source=src, n=len(held), prauc=pa, note=""))
    print(f"  {src}: PR-AUC={pa:.4f} (n={len(held)})", flush=True)

# ── Write report ──────────────────────────────────────────────────────────────
def _f(v):
    return f"{v:.4f}" if not (isinstance(v, float) and v != v) else "n/a"

lines = [
    "# Email Baseline Report (HashingVectorizer + SGDClassifier)\n",
    "## Test-split metrics",
    f"- ROC AUC:                      {_f(r_test['roc'])}",
    f"- PR AUC:                       {_f(r_test['prauc'])}",
    f"- Precision (PHISHING thr):     {_f(r_test['prec'])}",
    f"- Recall    (PHISHING thr):     {_f(r_test['rec'])}",
    f"- F1        (PHISHING thr):     {_f(r_test['f1'])}",
    f"\n### Confusion matrix (PHISHING threshold)\n```\n{r_test['cm']}\n```",
    f"\n### False-positive rates on test",
    f"- Ham  FPR: {ham_fpr:.4f}  ({ham_fpr*100:.2f}%)",
    f"- Spam FPR: {spam_fpr:.4f}  ({spam_fpr*100:.2f}%)",
    "\n## Golden-set metrics (24 hand-written Indian-context emails)",
    f"- ROC AUC:  {_f(r_gold['roc'])}",
    f"- PR AUC:   {_f(r_gold['prauc'])}",
    f"- F1:       {_f(r_gold['f1'])}",
    f"\n### Confusion matrix (golden)\n```\n{r_gold['cm']}\n```",
    "\n## Leave-one-source-out PR-AUC",
    "| Source | N | PR-AUC | Note |",
    "|--------|---|--------|------|",
]
for res in loso:
    lines.append(f"| {res['source']} | {res['n']} | {_f(res['prauc'])} | {res['note']} |")

lines += [
    "\n## Thresholds (chosen on val, <=1% ham FPR)",
    f"- phishing_threshold:   {phishing_thr:.6f}",
    f"- suspicious_threshold: {suspicious_thr:.6f}",
    f"\n## Latency",
    f"- CPU latency (hashing vec + SGD): {latency_ms:.2f} ms/email",
    "",
]

report_text = "\n".join(lines)
REPORT_PATH.write_text(report_text, encoding="utf-8")

print(f"\nReport written to {REPORT_PATH}")
print("\n" + "=" * 60)
print(report_text)
print("=" * 60)
print("BASELINE DONE", flush=True)
