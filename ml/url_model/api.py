import json
import pathlib
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from catboost import CatBoostClassifier

# Paths to saved artifacts
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "ml" / "url_model" / "artifacts" / "url_model.cbm"
THRESHOLDS_PATH = PROJECT_ROOT / "ml" / "url_model" / "artifacts" / "thresholds.json"

# Load model and thresholds at startup
model = CatBoostClassifier()
model.load_model(str(MODEL_PATH))
with open(THRESHOLDS_PATH, "r", encoding="utf-8") as f:
    thresholds = json.load(f)
phishing_thr = thresholds["phishing_threshold"]
suspicious_thr = thresholds["suspicious_threshold"]

# Import feature extraction and normalisation
from ml.url_model.features import extract_features
from ml.shared.normalisation import norm

app = FastAPI(
    title="AI-GovShield URL Classification API",
    description="Predict phishing / suspicious scores for a URL using the trained CatBoost model.",
)


class PredictRequest(BaseModel):
    url: HttpUrl


class PredictResponse(BaseModel):
    url: str
    url_norm: str
    phishing_score: float
    suspicious_score: float
    phishing_label: Literal[0, 1]
    suspicious_label: Literal[0, 1]
    message: str


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    raw_url = str(req.url)
    # Normalise the URL exactly as training did; raw_url kept for response and future gov check
    url_normalized = norm(raw_url)
    df = pd.DataFrame({"url_norm": [url_normalized]})
    try:
        features = extract_features(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Feature extraction failed: {e}")
    # Ensure categorical column is string (CatBoost expects this)
    features["tld"] = features["tld"].astype(str)
    # Obtain probability of the positive class (phishing)
    prob = model.predict_proba(features)[:, 1][0]
    phishing_label = int(prob >= phishing_thr)
    suspicious_label = int(prob >= suspicious_thr)
    message = (
        "phishing" if phishing_label else ("suspicious" if suspicious_label else "legitimate")
    )
    return PredictResponse(
        url=raw_url,
        url_norm=url_normalized,
        phishing_score=prob,
        suspicious_score=prob,
        phishing_label=phishing_label,
        suspicious_label=suspicious_label,
        message=message,
    )

# Run locally with: uvicorn ml.url_model.api:app --host 0.0.0.0 --port 8000
