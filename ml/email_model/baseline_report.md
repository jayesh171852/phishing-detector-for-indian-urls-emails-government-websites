# Email Baseline Report (HashingVectorizer + SGDClassifier)

## Test-split metrics
- ROC AUC:                      0.9938
- PR AUC:                       0.9265
- Precision (PHISHING thr):     0.8402
- Recall    (PHISHING thr):     0.9535
- F1        (PHISHING thr):     0.8933

### Confusion matrix (PHISHING threshold)
```
[[6649   82]
 [  21  431]]
```

### False-positive rates on test
- Ham  FPR: 0.0014  (0.14%)
- Spam FPR: 0.0253  (2.53%)

## Golden-set metrics (24 hand-written Indian-context emails)
- ROC AUC:  0.4861
- PR AUC:   0.5955
- F1:       0.3529

### Confusion matrix (golden)
```
[[10  2]
 [ 9  3]]
```

## Leave-one-source-out PR-AUC
| Source | N | PR-AUC | Note |
|--------|---|--------|------|
| Enron | 27256 | n/a | single class |
| CEAS_08 | 31614 | n/a | single class |
| SpamAssasin | 5598 | n/a | single class |
| Nigerian_Fraud | 3125 | n/a | single class |
| Nazario | 1500 | n/a | single class |
| Ling | 2828 | n/a | single class |
| handwritten_golden_india | 0 | n/a | single class |

## Thresholds (chosen on val, <=1% ham FPR)
- phishing_threshold:   0.474312
- suspicious_threshold: 0.688442

## Latency
- CPU latency (hashing vec + SGD): 5.22 ms/email
