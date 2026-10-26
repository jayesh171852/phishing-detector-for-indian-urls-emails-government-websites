import os
print('=== URL Model Training Started ===')
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from catboost import CatBoostClassifier, Pool

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)

# Add project root to sys.path for relative imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from ml.shared.config import DATA_DIR
from ml.url_model.features import extract_features

# Paths
TRAIN_CSV = Path(DATA_DIR) / "train_urls.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = OUTPUT_DIR / "url_model.cbm"
THRESHOLDS_PATH = OUTPUT_DIR / "thresholds.json"
REPORT_PATH = Path(__file__).resolve().parent / "eval_report.md"

# Load data
cols = ["url_norm", "label", "split", "url"]  # include raw url for potential debugging
df = pd.read_csv(TRAIN_CSV, usecols=cols)

# Split according to the provided splits
train_df = df[df["split"] == "train"]
val_df   = df[df["split"] == "val"]
test_df  = df[df["split"] == "test"]
gov_test_df = df[df["split"] == "gov_test"]

# Feature extraction
X_train = extract_features(train_df)
X_val   = extract_features(val_df)
X_test  = extract_features(test_df)
X_gov_test = extract_features(gov_test_df)

y_train = train_df["label"].values
y_val   = val_df["label"].values
y_test  = test_df["label"].values

y_gov_test = gov_test_df["label"].values

# Ensure the TLD column is treated as categorical (string) for CatBoost
for df_feat in [X_train, X_val, X_test, X_gov_test]:
    df_feat["tld"] = df_feat["tld"].astype(str)

# CatBoost expects categorical feature names (or indices). We'll pass the name.
categorical_features = ["tld"]

model = CatBoostClassifier(
    iterations=500,
    depth=8,
    learning_rate=0.1,
    loss_function="Logloss",
    eval_metric="AUC",

    verbose=False,
    random_seed=42,
    early_stopping_rounds=50,
)

# Train with validation set for early stopping
cat_feature_idx = [X_train.columns.get_loc('tld')]
train_pool = Pool(data=X_train, label=y_train, cat_features=cat_feature_idx)
val_pool   = Pool(data=X_val,   label=y_val,   cat_features=cat_feature_idx)
model.fit(train_pool, eval_set=val_pool, use_best_model=True)
print('Model training completed')

# Calibration on validation set – isotonic (5‑fold CV) using combined train+val


# Save CatBoost model (the raw model; calibrated probabilities are obtained via calibrator)
model.save_model(str(MODEL_PATH))

# Determine thresholds on validation set (still using original X_val for thresholds)
val_probs = model.predict_proba(val_pool)[:, 1]
print('Validation probabilities computed')
# PHISHING threshold – max prob such that false‑positive rate <= 1% on legit (label 0)
legit_mask = y_val == 0
legit_probs = val_probs[legit_mask]
sorted_legit = sorted(legit_probs, reverse=True)
idx_fp1 = max(int(len(sorted_legit) * 0.01) - 1, 0)
phishing_thr = sorted_legit[idx_fp1] if sorted_legit else 1.0

# SUSPICIOUS threshold – probability giving ~90% recall on positives
pos_mask = y_val == 1
pos_probs = val_probs[pos_mask]
sorted_pos = sorted(pos_probs, reverse=True)
recall_target = 0.90
idx_rec = int(len(sorted_pos) * recall_target) - 1
suspicious_thr = sorted_pos[idx_rec] if sorted_pos else 0.0

thresholds = {
    "phishing_threshold": phishing_thr,
    "suspicious_threshold": suspicious_thr,
}
with open(THRESHOLDS_PATH, "w", encoding="utf-8") as f:
    json.dump(thresholds, f, indent=2)

# Evaluation on test split using encoded test data
test_probs = model.predict_proba(X_test)[:, 1]
print('Test probabilities computed')
pred_phish = (test_probs >= phishing_thr).astype(int)
pred_susp  = (test_probs >= suspicious_thr).astype(int)

# Gov-test evaluation using encoded gov_test data
gov_probs = model.predict_proba(X_gov_test)[:, 1]

# Save CatBoost model (the raw model; calibrated probabilities are obtained via calibrator)
model.save_model(str(MODEL_PATH))



def fmt_metric(name, value):
    return f"- **{name}**: {value:.4f}\n"

with open(REPORT_PATH, "w", encoding="utf-8") as report:
    report.write("# URL Model Evaluation Report\n\n")
    report.write("## Metrics on Test Split\n")
    report.write(fmt_metric("ROC AUC", roc_auc_score(y_test, test_probs)))
    report.write(fmt_metric("PR AUC", average_precision_score(y_test, test_probs)))
    report.write(fmt_metric("Precision (PHISHING thresh)", precision_score(y_test, pred_phish)))
    report.write(fmt_metric("Recall (PHISHING thresh)", recall_score(y_test, pred_phish)))
    report.write(fmt_metric("F1 (PHISHING thresh)", f1_score(y_test, pred_phish)))
    report.write("\n### Confusion Matrix (PHISHING threshold)\n```")
    report.write(str(confusion_matrix(y_test, pred_phish)))
    report.write("```\n\n")
    report.write(fmt_metric("Precision (SUSPICIOUS thresh)", precision_score(y_test, pred_susp)))
    report.write(fmt_metric("Recall (SUSPICIOUS thresh)", recall_score(y_test, pred_susp)))
    report.write(fmt_metric("F1 (SUSPICIOUS thresh)", f1_score(y_test, pred_susp)))
    report.write("\n### Confusion Matrix (SUSPICIOUS threshold)\n```")
    report.write(str(confusion_matrix(y_test, pred_susp)))
    report.write("```\n\n")
    report.write("## Gov‑test false‑positives (sample)\n")
    gov_probs = model.predict_proba(X_gov_test)[:, 1]
    fp_mask = (gov_probs >= phishing_thr) & (y_gov_test == 0)
    fp_positions = np.where(fp_mask)[0][:20]
    if fp_positions.size > 0:
        report.write("Samples where legit gov URLs were flagged as PHISHING:\n")
        for pos in fp_positions:
            url = gov_test_df.iloc[pos]["url"]
            prob = gov_probs[pos]
            report.write(f"- {url} (prob={prob:.4f})\n")
    else:
        report.write("No false‑positives on gov_test split at PHISHING threshold.\n")

print("Training and evaluation completed. Model saved to", MODEL_PATH)
print("Thresholds saved to", THRESHOLDS_PATH)
print("Report written to", REPORT_PATH)
