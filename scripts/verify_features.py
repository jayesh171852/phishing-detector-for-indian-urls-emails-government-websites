"""
Phase 1 verification script (read-only).
Loads train_urls.csv, extracts features for all rows, verifies:
  - feature list exactly matches the 21 spec-required names in order
  - prints one example feature-row each for three URLs (passed through norm)
  - prints extraction time for 1,000 URLs
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from ml.shared.config import DATA_DIR
from ml.shared.normalisation import norm
from ml.url_model.features import extract_features

# ── Spec-required feature list (order matters) ──────────────────────────────
SPEC_FEATURES = [
    "url_length", "host_length", "path_length", "query_length",
    "num_dots", "num_hyphens", "num_digits", "digit_ratio",
    "num_special_chars", "num_subdomains", "path_depth",
    "host_entropy", "path_entropy", "longest_token_len",
    "vowel_ratio_host", "has_ip_host", "has_at_symbol",
    "has_punycode", "keyword_count", "is_url_shortener", "tld",
]

# ── Load data ────────────────────────────────────────────────────────────────
print(f"\nDATA_DIR = {DATA_DIR}")
train_path = Path(DATA_DIR) / "train_urls.csv"
print(f"Loading {train_path} …")
df = pd.read_csv(train_path)
print(f"Loaded {len(df)} rows.")

# ── Extract features for all rows ───────────────────────────────────────────
print("\nExtracting features for all rows …")
t0 = time.time()
feats = extract_features(df)
elapsed_all = time.time() - t0
print(f"Extracted {len(df)} rows in {elapsed_all:.2f}s")

# ── Verify feature list ──────────────────────────────────────────────────────
actual = list(feats.columns)
print(f"\nFeature list ({len(actual)} features):")
for i, name in enumerate(actual, 1):
    print(f"  {i:2d}. {name}")

if actual == SPEC_FEATURES:
    print("\nASSERT PASSED: feature list matches spec exactly (21 features, correct order).")
else:
    missing = [f for f in SPEC_FEATURES if f not in actual]
    extra   = [f for f in actual if f not in SPEC_FEATURES]
    wrong_order = actual != SPEC_FEATURES
    print(f"\nASSERT FAILED:")
    if missing:
        print(f"  Missing from features.py: {missing}")
    if extra:
        print(f"  Extra in features.py:     {extra}")
    if wrong_order and not missing and not extra:
        print(f"  Order mismatch. Got: {actual}")
    sys.exit(1)

# ── Example rows ─────────────────────────────────────────────────────────────
test_urls = [
    "https://uidai.gov.in/en/my-aadhaar",
    "https://uidai-aadhar-update.xyz/login",
    "https://google.com",
]

print("\n── Example feature rows ─────────────────────────────────────────────────")
for raw in test_urls:
    url_n = norm(raw)
    row_df = pd.DataFrame({"url_norm": [url_n]})
    row_feats = extract_features(row_df).iloc[0]
    print(f"\n  URL      : {raw}")
    print(f"  url_norm : {url_n}")
    for fname in SPEC_FEATURES:
        print(f"    {fname:<22} = {row_feats[fname]}")

# ── Speed on 1,000 rows ──────────────────────────────────────────────────────
print("\n── Speed test (1,000 rows) ──────────────────────────────────────────────")
df1k = df.head(1000)
t1 = time.time()
_ = extract_features(df1k)
elapsed_1k = time.time() - t1
print(f"1,000 rows extracted in {elapsed_1k:.3f}s  ({'PASS' if elapsed_1k < 5.0 else 'FAIL — over 5s'})")

print("\n=== Phase 1 verification complete ===")
