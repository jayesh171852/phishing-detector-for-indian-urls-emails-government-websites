# AI-GovShield v2: spec (source of truth)

## Rules for the agent
1. Read this file at the start of every session. If it conflicts with the code or a request, stop and ask.
2. One phase per session. Stop at the phase's STOP point and wait for my approval.
3. Report only raw terminal output you actually ran; write "not run" otherwise. Never say a phase is complete without pasting the output of its Done-when checks.
4. Write the minimum code. No frameworks beyond the stack below without asking. No network calls in training or inference code.
5. Never modify or delete files in DATA_DIR. Use no data from outside DATA_DIR.
6. Commit to git after each approved phase.

## Goal
A Chrome extension plus FastAPI backend that, in real time, classifies the page a user visits or the email they open: LEGIT_GOV, LEGIT, SUSPICIOUS, PHISHING, PHISHING_GOV (emails: LEGIT, SUSPICIOUS, PHISHING), and explains why. Failure to avoid: real URLs flagged as fake government sites because of dataset shortcuts and train/serve mismatch.

## Architecture (follows the project slide, steps 1 to 8)
1 user opens a website or email -> 2 Chrome extension (Plasmo, Manifest V3) -> 3 extract URL and/or email subject, body, links -> 4A ModernBERT email analysis -> 4B email risk 0-100; 4C URL feature extraction -> 4D CatBoost -> 4E government verification (.gov.in/.nic.in rules, allowlist, PhishTank-style blocklist, impersonation similarity) -> 4F URL risk 0-100 -> 5 risk fusion engine -> 6 SHAP -> 7 explainable prediction (risk level + reasons) -> 8 browser popup (confidence donut, explanation bullets, safety tips). Design choices: the URL model uses lexical features only. WHOIS, SSL, DNS and HTML checks (slide step 4C) are optional asynchronous evidence added in Phase 8, not model inputs, because no training data has them and they would break the latency and privacy goals. Risk levels: LOW, MEDIUM, HIGH.

## Tech stack (fixed)
- Extension: Plasmo, React, TypeScript, Manifest V3.
- Backend: Python 3.13, FastAPI, Uvicorn, Pydantic v2, loguru.
- URL model: CatBoost, scikit-learn, SHAP (TreeExplainer), rapidfuzz, tldextract, idna.
- Email model: Hugging Face Transformers (answerdotai/ModernBERT-base), PyTorch, scikit-learn baseline, optional ONNX Runtime export.
- Tests: pytest, httpx.

## Data (all in DATA_DIR = C:\\Users\\jayes\\OneDrive\\Desktop\\pbl sem 5\\new; read through ml/shared/config.py only)
- train_urls.csv: 61,720 rows x 10 columns (url, url_norm, label, source, group, reg_domain, group_key, split, date, target). label 1 = PHISHING, 0 = LEGIT everywhere. Label counts: 0 = 33,575 (including 5,430 real gov URLs), 1 = 28,145. Splits are grouped by domain: never create new random splits. split counts: train 41,430, val 7,393, test 8,037, gov_test 4,860. Group gov_in = real .gov.in/.nic.in URLs (label 0): 570 rows in train, 4,860 in gov_test (false-positive evaluation only). It is the only file the URL trainer reads.
- gov_eval_set.csv: 517 rows (url, expected_verdict, acceptable_verdicts, category, source, needs_review, note). Evaluates the government verifier only, reported per category. Never train or tune the ML model on it. Most lookalike rows are synthetic: do not tune rules until the synthetic rows reach 100%.
- official_domains_seed.csv: 1,260 domains; 1,233 verified by .gov.in/.nic.in suffix; 27 verified=no need manual verification against india.gov.in before being trusted.
- email_dataset.csv: 71,945 rows (id, source, kind, label, label_raw, split, text, link_domains, n_chars, dup_cluster). label 1 = phishing or 419 fraud, 0 = ham or spam. label_raw is the original dataset label (it lumped spam with phishing); never train on it. Positives: 4,637 (1,512 phishing, 3,125 fraud). Splits: train 57,542, val 7,196, test 7,183, golden 24 (never train on golden). Text is already cleaned (lowercase, links masked as [URL], addresses as [EMAIL]).
- email_golden_starter.csv: 24 hand-written Indian-context emails (optional — the same rows exist in email_dataset.csv with split == golden). tranco_GQ32K.csv (no header: rank,domain): reference for official gov domains and false-positive tests only.
- phishing_urls.csv and legit_urls.csv (if present): raw inputs already merged into train_urls.csv; never load them for training.
- EXCLUDE everything else: PhiUSIIL, "final dataset collection", "govtwebsites", old email source files, phishtank_clean.csv, any copy of these files outside DATA_DIR.
- Never use as features: label, label_raw, split, source, kind, group, group_key, reg_domain, date, target, id, dup_cluster.

## Normalisation (ml/shared/normalisation.py, used by training AND the API)
```python
from urllib.parse import urlparse

def norm(url):
    p = urlparse(str(url).strip()); netloc = p.netloc.lower()
    if netloc.startswith("www."): netloc = netloc[4:]
    path = "" if p.path in ("", "/") else p.path
    return netloc + path + (("?" + p.query) if p.query else "")
```
The URL trainer reads the url_norm column and asserts norm(url) == url_norm on every row. The API computes norm(raw_url) for the ML model only; the raw URL goes to the government verifier and the response.

## URL model (ml/url_model)
Features from url_norm only, with no scheme added back, no network, under 5 ms per URL: url_length, host_length, path_length, query_length, num_dots, num_hyphens, num_digits, digit_ratio, num_special_chars, num_subdomains, path_depth, host_entropy, path_entropy, longest_token_len, vowel_ratio_host, has_ip_host, has_at_symbol, has_punycode, keyword_count (login, verify, update, secure, account, bank, kyc, otp, refund, pay), is_url_shortener, tld (CatBoost categorical: top 50 TLDs, else "other").
FORBIDDEN: scheme/https, www, ports, SSL, WHOIS/age, page content, government-similarity features, hand-made TLD risk scores, double-slash flags.
Training: CatBoost; fit on split==train; early stopping and calibration (isotonic or Platt) on val; two thresholds chosen on val: PHISHING at <=1% false-positive rate on legit, SUSPICIOUS at about 90% recall; saved to artifacts/thresholds.json and read at inference (no hard-coded 0.5). Test is used once for the final report; gov_test only to count false positives. The loader asserts model.feature_names_ == extractor.feature_names, else logs ERROR and marks the model unavailable (no silent fallback). eval_report.md: test precision/recall/F1/ROC-AUC/PR-AUC, confusion matrices at both thresholds.

## Government verifier (government/gov_verifier.py: rules only, no network, under 5 ms)
Order, stop at the first match:
1. Confirmed blocklist (data/reference/blocklist.txt: exact URL or host, reloadable) -> PHISHING, even on gov.in.
2. urlparse(url).hostname (never substring search), lowercased, trailing dot removed: equals or ends with ".gov.in" or ".nic.in" at a label boundary -> LEGIT_GOV. This check applies even when the host contains xn-- (Punycode) labels — only government bodies can register under .gov.in / .nic.in so the suffix is trusted. Punycode suspicion (step 4's homograph check) applies only to hosts that do NOT end with .gov.in or .nic.in.
3. Allowlist data/reference/official_domains.csv (domain, organisation, category, verified, source_note) -> LEGIT_GOV; category psu_or_brand -> LEGIT.
4. Impersonation on any other host -> PHISHING_GOV only with evidence PLUS a risk factor. Evidence: gov keyword (uidai, aadhaar, aadhar, incometax, itr, epfo, digilocker, passport, parivahan, nvsp, pmkisan, umang, gst, mygov, cowin) in host or path; "gov.in", "nic.in" or "gov-in" outside the true suffix; rapidfuzz ratio >= 88 to an official label without being equal; homograph lookalike. Risk factor: cheap TLD, hyphen-heavy host, digits, free-hosting platform. Keyword only -> SUSPICIOUS.
5. Otherwise return None and fall through to the ML model.
official_domains.csv is built from official_domains_seed.csv; entries with verified=no stay untrusted until I confirm them.

## Email model (ml/email_model)
Input = the "text" column (cleaned subject [SEP] body). Inference must apply the identical cleaning in ml/shared/email_clean.py: strip HTML tags and unescape entities; mask URLs as [URL] and addresses as [EMAIL]; lowercase; remove spaces before punctuation; remove leading list tags like [name]; collapse whitespace; keep at most 2,400 characters (first 75% + last 25%). Train a TF-IDF + logistic regression baseline first. ModernBERT (answerdotai/ModernBERT-base): max 512 tokens, learning rate about 3e-5, batch 16 with gradient accumulation 2, 3 epochs, 10% warmup, weight decay 0.01, early stopping on validation PR-AUC, temperature scaling on val, thresholds chosen on val at <=1% false-positive rate on ham. Evaluate on test, on the golden rows, and leave-one-source-out (hold out each source in turn). Keep ModernBERT only if it clearly beats the baseline on leave-one-source-out and the golden set; otherwise ship the baseline. Report false-positive rates separately for ham and for spam. Links in an email are scored separately by the URL pipeline.

## Risk fusion, explanation and API
All scores are calibrated probabilities x 100. Rules in order: blocklist hit -> risk 100, HIGH; LEGIT_GOV -> risk min(URL score, 5), LOW; PHISHING_GOV -> risk max(90, URL score), HIGH; gov keyword only -> risk max(URL score, 40); website otherwise -> URL score. Email with links: p_links = highest link score after gov rules; risk = 100 x (1 - (1 - p_email)(1 - p_links)); add 20 if the text mentions a government brand and a link is not LEGIT_GOV; add 15 if a link's visible text shows one domain and its href another (cap 100). Levels use the saved thresholds: LOW below SUSPICIOUS, MEDIUM between, HIGH at or above PHISHING. Popup confidence = risk score for HIGH, 100 - risk for LOW.
Explanations: rule evidence first ("Pretends to be a government site (similar to uidai.gov.in) but is not on a .gov.in domain", "Listed in the blocklist", "Verified .gov.in domain"), then the top positive SHAP groups in plain language (link structure, randomly generated name, pressure words, risky domain ending, disguised address, shortened link). Email explanations are computed only on request.

Endpoints: POST /v1/analyze (url and/or email), POST /v1/url/check, POST /v1/email/check, POST /v1/feedback, GET /v1/blocklist (with version), GET /v1/health (model versions, feature-list check). Response fields: verdict, risk_score, risk_level, confidence, reasons[], tips[], evidence{gov, blocklist}, scores{url, email, links[]}, model_source (catboost | rule_fallback), model_version, latency_ms. The rule-based fallback runs only if the model file is missing or prediction throws; it logs a warning, has no HTTPS or SSL rule, and never treats .in, .gov.in or .nic.in as risky.

## Extension (extension/, Plasmo, MV3)
Files: background service worker, contents/gmail.ts and contents/outlook.ts, popup.tsx, options.tsx, tabs/warning.tsx. Permissions: storage, tabs, webNavigation, alarms, plus host permissions for the API and the supported webmail sites only. Navigation flow: skip non-http(s), localhost and private IPs; local .gov.in/.nic.in rule and a local blocklist first; cache (LOW 6 h, others 1 h); call the API with a 250 ms abort; on HIGH redirect to the warning page with "Go back" and "Proceed anyway"; on MEDIUM show a banner; on timeout allow with an "unchecked" badge. Email scanning is OFF until the user opts in; a privacy mode sends only host and path. Popup order: confidence donut with level colour, up to 3 reasons, 3 safety tips (do not share credentials, avoid clicking links, report suspicious activity), a "Report this verdict" button.

## Phases (one per session, STOP after each)
0. Setup (this task). Done when: layout exists, deps installed, check_data.py passes.
1. URL features: ml/url_model/features.py with the 21 features, no network. Done when: the numbers in Data match, norm(url)==url_norm for all rows, the feature list is printed, 1,000 URLs extract in under 5 s. STOP before training.
2. URL training and evaluation per "URL model". Done when: eval_report.md and thresholds.json exist; accuracy < 99.5%; gov_test false positives listed.
3. Government verifier + data/reference/official_domains.csv + scripts/eval_gov.py over gov_eval_set.csv with accuracy per category + tests/test_gov_verifier.py (uidai.gov.in.evil.xyz, evil.com/uidai.gov.in, uidai.gov.in@evil.com, uppercase hosts, trailing dots, ports). Done when: tests pass, per-category table printed, and the top-5,000 non-gov Tranco domains flagged PHISHING_GOV is printed (target 0).
4. Email: baseline, then ModernBERT, per "Email model". Done when: baseline and ModernBERT results (random, leave-one-source-out, golden, ham and spam false-positive rates) are printed; the CPU latency of the chosen model is printed. If there is no GPU, write the training as a script that runs on Colab or Kaggle and tell me.
5. Backend: /v1/analyze, fusion, SHAP reasons, schemas, model loader with the feature-list assertion, and tests/e2e_test.py. Done when: the API score equals the offline score on 100 rows from each split, a known phishing URL and a known legit URL are not inverted, and p95 latency of /v1/url/check is printed.
6. Extension URL flow and popup. Done when: it loads unpacked in Chrome, shows green on https://uidai.gov.in/, red or the warning page on a PhishTank-style lookalike, and I can see the popup.
7. Gmail/Outlook web content scripts and email scanning with opt-in. Done when: opening a test email shows the banner and marks risky links.
8. Optional async enrichment (WHOIS, DNS, SSL, HTML) shown as evidence only, then a hand‑labeled final test set with at least 30 items in each of the six categories (phishing site, legit site, phishing gov site, legit gov site, phishing email, legit email), accuracy reported per category, and the README.

## Progress log

| Phase | Status | Evidence |
|-------|--------|---------|
| 0 — Setup | VERIFIED | check_data.py passed (all checks OK, see Phase R run output) |
| 1 — URL features | VERIFIED | verify_features.py passed (21 features, correct order, 1000 URLs < 5s, see Phase R run output) |
| 2 — URL training | FILES PRESENT BUT UNVERIFIED | eval_report.md and thresholds.json exist; training not re-run in this session |
| 3 — Government verifier | VERIFIED | 21/21 pytest tests pass; eval_gov.py: real_gov 100%, real_gov_variant 100%, structural_trick 98%, lookalike 84.7%, hard_negative 68.6% (NONE = correct fall-through); 0 of top-5,000 Tranco domains flagged PHISHING_GOV |
| 4 — Email model | NOT STARTED | baseline.py and evaluate.py were corrupted; no email training code |
| 5 — Backend | NOT STARTED | backend/app/main.py was corrupted; no /v1/* routes exist |
| 6 — Extension | PARTIAL | Extension compiled to build/chrome-mv3-dev/; calls endpoints that don't exist yet |
| 7 — Gmail/Outlook | PARTIAL | Content scripts present; depends on missing email endpoint |
| 8 — Async enrichment | NOT STARTED | |

### Quarantined files (Phase R)
The following files were corrupted (contained shell-redirect artifacts) and moved to _quarantine/:
- ml/url_model/train.py → _quarantine/train.py
- ml/email_model/baseline.py → _quarantine/baseline.py
- ml/email_model/evaluate.py → _quarantine/evaluate.py
- ml/shared/email_clean.py → _quarantine/email_clean.py
- backend/app/main.py → _quarantine/main.py
- backend/app/schemas.py → _quarantine/schemas.py
- backend/app/services/__init__.py → _quarantine/services__init__.py
- README.md → _quarantine/README_corrupted.md

### Known issues
- 9 gov_test URLs with xn-- (Punycode) hosts flagged by ML model with probability > 0.998 (false positives); the government verifier (Phase 3) will handle these correctly once built.
- artifacts_all/ directory has unknown provenance — no script in the current codebase creates it; it may have been trained on a different data split.
- Extension was built early (build/chrome-mv3-dev/ exists) and calls /government-check, /explain, /predict-email endpoints that do not exist yet.
- DATA_DIR contains a stray url_model.cbm with unknown origin; MD5 confirms it is identical to artifacts/url_model.cbm (B8CFDFC457A1B0B38061F33B56BEC322); no current script writes to DATA_DIR.

-----SPEC END-----
