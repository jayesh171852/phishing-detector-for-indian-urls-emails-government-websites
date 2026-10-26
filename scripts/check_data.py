"""
Phase 0 data integrity check.
Reads DATA_DIR from ml.shared.config (env-var DATA_DIR or the default path).
Validates train_urls.csv and email_dataset.csv against the numbers in docs/SPEC.md.
Read-only: opens files but writes nothing.
"""
import sys
import os
from pathlib import Path

# ── Resolve project root so "ml" is importable ─────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from ml.shared.config import DATA_DIR
from ml.shared.normalisation import norm

ERRORS = []

def fail(msg):
    ERRORS.append(msg)
    print(f"  FAIL: {msg}")

def ok(msg):
    print(f"  OK  : {msg}")

# ── Required files ──────────────────────────────────────────────────────────
print(f"\nDATA_DIR = {DATA_DIR}\n")
print("=== Checking required files ===")

required = [
    "train_urls.csv",
    "gov_eval_set.csv",
    "official_domains_seed.csv",
    "email_dataset.csv",
    "tranco_GQ32K.csv",
]
optional = ["phishing_urls.csv", "legit_urls.csv", "email_golden_starter.csv"]

for fname in required:
    p = os.path.join(DATA_DIR, fname)
    if os.path.isfile(p):
        ok(f"{fname} present")
    else:
        fail(f"{fname} MISSING")

for fname in optional:
    p = os.path.join(DATA_DIR, fname)
    if os.path.isfile(p):
        ok(f"{fname} present (optional)")
    else:
        print(f"  WARN: {fname} not found (optional — skipping)")

if ERRORS:
    print(f"\n{len(ERRORS)} required file(s) missing. Aborting.")
    sys.exit(1)

# ── train_urls.csv ──────────────────────────────────────────────────────────
print("\n=== Checking train_urls.csv ===")
train_path = os.path.join(DATA_DIR, "train_urls.csv")
try:
    df = pd.read_csv(train_path)
except Exception as e:
    fail(f"Cannot read train_urls.csv: {e}")
    sys.exit(1)

# Shape
expected_rows, expected_cols = 61720, 10
if df.shape == (expected_rows, expected_cols):
    ok(f"shape = {df.shape}")
else:
    fail(f"shape = {df.shape} — expected ({expected_rows}, {expected_cols})")

# Columns
required_cols = {"url", "url_norm", "label", "source", "group",
                 "reg_domain", "group_key", "split", "date", "target"}
missing_cols = required_cols - set(df.columns)
if missing_cols:
    fail(f"Missing columns: {missing_cols}")
else:
    ok(f"All 10 required columns present")

# Label counts  (0: 33575, 1: 28145)
counts = df["label"].value_counts().to_dict()
exp_label = {0: 33575, 1: 28145}
for lbl, exp in exp_label.items():
    got = counts.get(lbl, 0)
    if got == exp:
        ok(f"label {lbl} count = {got}")
    else:
        fail(f"label {lbl} count = {got} — expected {exp}")

# Split counts  (train 41430, val 7393, test 8037, gov_test 4860)
scounts = df["split"].value_counts().to_dict()
exp_splits = {"train": 41430, "val": 7393, "test": 8037, "gov_test": 4860}
for sp, exp in exp_splits.items():
    got = scounts.get(sp, 0)
    if got == exp:
        ok(f"split '{sp}' count = {got}")
    else:
        fail(f"split '{sp}' count = {got} — expected {exp}")

# norm(url) == url_norm on ALL rows
print("  Checking norm(url) == url_norm for ALL rows (may take a few seconds)…")
mismatches = []
for idx, row in df.iterrows():
    computed = norm(str(row["url"]))
    stored = str(row["url_norm"])
    if computed != stored:
        mismatches.append((idx, row["url"], stored, computed))
        if len(mismatches) >= 5:
            break  # report first 5 only
if mismatches:
    for idx, url, stored, computed in mismatches:
        fail(f"norm mismatch row {idx}: url={url!r} stored={stored!r} computed={computed!r}")
else:
    ok(f"norm(url) == url_norm for all {len(df)} rows")

# No group_key in more than one of train/val/test
print("  Checking group_key does not leak across splits…")
for gk, grp in df[df["split"].isin(["train", "val", "test"])].groupby("group_key"):
    splits_present = set(grp["split"].unique())
    if len(splits_present) > 1:
        fail(f"group_key {gk!r} appears in splits: {splits_present}")
        break
else:
    ok("No group_key appears in more than one of train/val/test")

# ── email_dataset.csv ───────────────────────────────────────────────────────
print("\n=== Checking email_dataset.csv ===")
email_path = os.path.join(DATA_DIR, "email_dataset.csv")
try:
    em = pd.read_csv(email_path)
except Exception as e:
    fail(f"Cannot read email_dataset.csv: {e}")
    sys.exit(1)

exp_email_rows, exp_email_cols = 71945, 10
if em.shape == (exp_email_rows, exp_email_cols):
    ok(f"shape = {em.shape}")
else:
    fail(f"shape = {em.shape} — expected ({exp_email_rows}, {exp_email_cols})")

ecounts = em["label"].value_counts().to_dict()
exp_email_labels = {0: 67308, 1: 4637}
for lbl, exp in exp_email_labels.items():
    got = ecounts.get(lbl, 0)
    if got == exp:
        ok(f"label {lbl} count = {got}")
    else:
        fail(f"label {lbl} count = {got} — expected {exp}")

escounts = em["split"].value_counts().to_dict()
exp_email_splits = {"train": 57542, "val": 7196, "test": 7183, "golden": 24}
for sp, exp in exp_email_splits.items():
    got = escounts.get(sp, 0)
    if got == exp:
        ok(f"split '{sp}' count = {got}")
    else:
        fail(f"split '{sp}' count = {got} — expected {exp}")

# ── Final summary ────────────────────────────────────────────────────────────
print("\n=== Summary ===")
if ERRORS:
    print(f"FAILED — {len(ERRORS)} check(s) did not pass:")
    for e in ERRORS:
        print(f"  • {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
