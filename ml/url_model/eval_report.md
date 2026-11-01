# URL Model Evaluation Report

## Metrics on Test Split
- **ROC AUC**: 0.9490
- **PR AUC**: 0.9474
- **Precision (PHISHING thresh)**: 0.9799
- **Recall (PHISHING thresh)**: 0.6843
- **F1 (PHISHING thresh)**: 0.8058

### Confusion Matrix (PHISHING threshold)
```[[4279   52]
 [1170 2536]]```

- **Precision (SUSPICIOUS thresh)**: 0.7580
- **Recall (SUSPICIOUS thresh)**: 0.9323
- **F1 (SUSPICIOUS thresh)**: 0.8362

### Confusion Matrix (SUSPICIOUS threshold)
```[[3228 1103]
 [ 251 3455]]```

## Gov‑test false‑positives (sample)
Samples where legit gov URLs were flagged as PHISHING:
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/scheme/financial-assistance-families-west-pakistani-refugees-wprs (prob=0.9981)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/scheme/aapda-mitra-scheme (prob=0.9981)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/rules-data (prob=1.0000)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/media-videos (prob=1.0000)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/key-person/nityanand-rai (prob=0.9981)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/gazette-notifications (prob=0.9981)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/ (prob=1.0000)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/key-person/amit-shah (prob=0.9981)
- https://xn--i1b5bzbybhfo5c8b4bxh.xn--11b7cb3a6a.xn--h2brj9c/visitors-pass (prob=1.0000)
