# Email datasets

## Generated source data

- `generated/email_indian_train.csv` contains 5,000 synthetic Indian-context
  training examples.
- `generated/email_holdout_families.csv` contains 800 synthetic examples from
  families excluded from training.

## Model-ready data

- `processed/email_dataset_augmented.csv` combines the canonical dataset with
  the generated training examples.
- `processed/email_holdout_clean.csv` contains the cleaned holdout examples
  used only for evaluation.

Keep the holdout dataset out of all training runs.
