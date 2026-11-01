"""Prepare an augmented email dataset without modifying the canonical DATA_DIR."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ml.shared.email_clean import clean


def convert_generated(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"subject", "body", "label"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    return pd.DataFrame(
        {
            "text": [
                clean(subject, body)
                for subject, body in zip(frame["subject"], frame["body"])
            ],
            "label": frame["label"].astype(int),
            "split": "train",
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--train-extra", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--holdout-output", type=Path, required=True)
    args = parser.parse_args()

    base = pd.read_csv(args.base)
    required = {"text", "label", "split"}
    missing = required - set(base.columns)
    if missing:
        raise ValueError(f"{args.base} is missing columns: {sorted(missing)}")

    extra = convert_generated(args.train_extra)
    augmented = pd.concat([base, extra], ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    augmented.to_csv(args.output, index=False)
    convert_generated(args.holdout).drop(columns="split").to_csv(
        args.holdout_output, index=False
    )
    print(f"wrote augmented rows={len(augmented)} train_extra={len(extra)}")
    print(f"wrote holdout rows={len(pd.read_csv(args.holdout))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
