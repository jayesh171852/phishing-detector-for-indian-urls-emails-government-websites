"""
scripts/eval_gov.py
-------------------
Evaluate government/gov_verifier.py against DATA_DIR/gov_eval_set.csv.
Prints a per-category accuracy table and an overall summary.
Read-only — writes nothing.

Usage:
    python scripts/eval_gov.py
"""
import sys
import time
from pathlib import Path
from collections import defaultdict

# ── Make project root importable ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from ml.shared.config import DATA_DIR
from government.gov_verifier import GovVerifier

# ── Load eval set ────────────────────────────────────────────────────────────
eval_path = Path(DATA_DIR) / "gov_eval_set.csv"
df = pd.read_csv(eval_path)
print(f"\nLoaded {len(df)} rows from {eval_path}")
print("Categories:", dict(df["category"].value_counts()))

verifier = GovVerifier()

# ── Run ──────────────────────────────────────────────────────────────────────
results = []
t0 = time.perf_counter()
for _, row in df.iterrows():
    url      = row["url"]
    expected = row["expected_verdict"].strip()
    # acceptable_verdicts is a pipe-separated list
    acceptable = {v.strip() for v in str(row["acceptable_verdicts"]).split("|")}

    result = verifier.check(url)
    got    = result.verdict if result is not None else "NONE"

    # A result is correct if it matches any acceptable verdict
    correct = got in acceptable
    results.append({
        "url":        url,
        "category":   row["category"],
        "expected":   expected,
        "acceptable": acceptable,
        "got":        got,
        "correct":    correct,
        "reason":     result.reason if result else "",
    })
elapsed = time.perf_counter() - t0

# ── Per-category table ───────────────────────────────────────────────────────
cat_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "correct": 0, "errors": []})
for r in results:
    c = r["category"]
    cat_stats[c]["total"] += 1
    if r["correct"]:
        cat_stats[c]["correct"] += 1
    else:
        cat_stats[c]["errors"].append(r)

print("\n" + "=" * 72)
print(f"{'Category':<22}  {'Correct':>7}  {'Total':>5}  {'Accuracy':>9}")
print("-" * 72)
for cat in sorted(cat_stats):
    s = cat_stats[cat]
    acc = s["correct"] / s["total"] * 100
    print(f"  {cat:<20}  {s['correct']:>7}  {s['total']:>5}  {acc:>8.1f}%")
total_correct = sum(r["correct"] for r in results)
total = len(results)
print("-" * 72)
print(f"  {'OVERALL':<20}  {total_correct:>7}  {total:>5}  {total_correct/total*100:>8.1f}%")
print("=" * 72)

# ── Print first 5 errors per category ────────────────────────────────────────
any_errors = False
for cat in sorted(cat_stats):
    errs = cat_stats[cat]["errors"]
    if not errs:
        continue
    any_errors = True
    print(f"\nErrors in '{cat}' ({len(errs)} total — showing first 5):")
    for e in errs[:5]:
        print(f"  URL      : {e['url']}")
        print(f"  Expected : {e['expected']}  |  Acceptable: {e['acceptable']}")
        print(f"  Got      : {e['got']}  —  {e['reason']}")
        print()

if not any_errors:
    print("\nNo errors.")

print(f"\nTotal rows: {total}  |  Elapsed: {elapsed:.2f}s  "
      f"({elapsed/total*1000:.2f} ms/URL average)")
