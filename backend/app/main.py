from __future__ import annotations

import json
import pathlib
import time
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from catboost import CatBoostClassifier

from backend.app.schemas import (
    AnalyzeRequest,
    CheckResponse,
    EmailCheckRequest,
    FeedbackRequest,
    HealthResponse,
    URLCheckRequest,
)
from government.gov_verifier import GovVerifier
from ml.shared.email_clean import clean
from ml.shared.normalisation import norm
from ml.url_model.features import bucket_tld, extract_features

ROOT = pathlib.Path(__file__).resolve().parents[2]
URL_ARTIFACTS = ROOT / "ml" / "url_model" / "artifacts"
EMAIL_ARTIFACTS = ROOT / "ml" / "email_model" / "artifacts"

app = FastAPI(title="AI-GovShield API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

gov_verifier = GovVerifier()
url_model = CatBoostClassifier()
url_model.load_model(str(URL_ARTIFACTS / "url_model.cbm"))
url_thresholds = json.loads((URL_ARTIFACTS / "thresholds.json").read_text(encoding="utf-8"))
url_features = json.loads((URL_ARTIFACTS / "feature_names.json").read_text(encoding="utf-8"))
tld_vocabulary = json.loads((URL_ARTIFACTS / "tld_vocabulary.json").read_text(encoding="utf-8"))
url_calibrator = joblib.load(URL_ARTIFACTS / "calibrator.joblib")

email_vec = joblib.load(EMAIL_ARTIFACTS / "vec.pkl")
email_model = joblib.load(EMAIL_ARTIFACTS / "logreg.pkl")
email_thresholds = json.loads((EMAIL_ARTIFACTS / "thresholds.json").read_text(encoding="utf-8"))

try:
    import shap

    url_explainer = shap.TreeExplainer(url_model)
except Exception:
    url_explainer = None


def _level(score: float) -> str:
    if score >= url_thresholds["phishing_threshold"] * 100:
        return "HIGH"
    if score >= url_thresholds["suspicious_threshold"] * 100:
        return "MEDIUM"
    return "LOW"


def _url_score(raw_url: str) -> tuple[float, list[str], dict[str, Any], str]:
    normalized = norm(raw_url)
    gov = gov_verifier.check(raw_url)
    if gov is not None:
        if gov.verdict == "LEGIT_GOV":
            return 0.0, [gov.reason], {"gov": gov.verdict, "matched": gov.matched}, "rule_fallback"
        if gov.verdict in {"PHISHING", "PHISHING_GOV"}:
            return 100.0, [gov.reason], {"gov": gov.verdict, "matched": gov.matched}, "rule_fallback"
        if gov.verdict == "SUSPICIOUS":
            return 40.0, [gov.reason], {"gov": gov.verdict, "matched": gov.matched}, "rule_fallback"

    features = extract_features(pd.DataFrame({"url_norm": [normalized]}))
    features["tld"] = features["tld"].map(lambda value: bucket_tld(value, tld_vocabulary)).astype(str)
    if list(features.columns) != url_features:
        raise RuntimeError("URL feature manifest mismatch")
    model_features = list(getattr(url_model, "feature_names_", []))
    if model_features and model_features != url_features:
        raise RuntimeError("Saved model feature manifest mismatch")
    probability = float(url_calibrator.predict(url_model.predict_proba(features)[:, 1])[0])
    reasons: list[str] = []
    if url_explainer is not None:
        try:
            values = url_explainer.shap_values(features)
            values = values[1][0] if isinstance(values, list) else values[0]
            ranked = sorted(zip(features.columns, values), key=lambda item: abs(item[1]), reverse=True)
            reasons.extend(f"{name} contributes {'risk' if value > 0 else 'safety'}" for name, value in ranked[:3] if value)
        except Exception:
            reasons = []
    return probability * 100, reasons, {"gov": None, "url_norm": normalized}, "catboost"


def _response(verdict: str, score: float, reasons: list[str], evidence: dict[str, Any], scores: dict[str, Any], source: str, started: float) -> CheckResponse:
    return CheckResponse(
        verdict=verdict,
        risk_score=round(score, 4),
        risk_level=_level(score),
        confidence=round(score if score >= 50 else 100 - score, 4),
        reasons=reasons[:5],
        tips=["Do not share credentials.", "Avoid clicking suspicious links.", "Report suspicious activity."],
        evidence=evidence,
        scores=scores,
        model_source=source,
        model_version="url-catboost-v2",
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0", models={"url": True, "email": True}, feature_list_ok=url_features == list(url_model.feature_names_))


@app.post("/v1/url/check", response_model=CheckResponse)
def check_url(request: URLCheckRequest) -> CheckResponse:
    started = time.perf_counter()
    try:
        score, reasons, evidence, source = _url_score(request.url)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    verdict = "PHISHING" if score >= url_thresholds["phishing_threshold"] * 100 else "SUSPICIOUS" if score >= url_thresholds["suspicious_threshold"] * 100 else "LEGIT"
    return _response(verdict, score, reasons, evidence, {"url": score}, source, started)


@app.post("/v1/email/check", response_model=CheckResponse)
def check_email(request: EmailCheckRequest) -> CheckResponse:
    started = time.perf_counter()
    text = clean(request.subject, request.body)
    score = float(email_model.predict_proba(email_vec.transform([text]))[:, 1][0] * 100)
    threshold = email_thresholds["phishing_threshold"] * 100
    verdict = "PHISHING" if score >= threshold else "LEGIT"
    return _response(verdict, score, [], {"email": verdict}, {"email": score, "url": None}, "baseline", started)


@app.post("/v1/analyze", response_model=CheckResponse)
def analyze(request: AnalyzeRequest) -> CheckResponse:
    if request.url:
        return check_url(URLCheckRequest(url=request.url))
    if request.subject is not None or request.body is not None:
        return check_email(EmailCheckRequest(subject=request.subject or "", body=request.body or ""))
    raise HTTPException(status_code=422, detail="url or email content is required")


@app.post("/v1/feedback")
def feedback(request: FeedbackRequest) -> dict[str, str]:
    return {"status": "accepted"}


@app.get("/v1/blocklist")
def blocklist() -> dict[str, Any]:
    path = ROOT / "data" / "reference" / "blocklist.txt"
    entries = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    return {"version": str(path.stat().st_mtime_ns), "count": len(entries), "entries": entries}
