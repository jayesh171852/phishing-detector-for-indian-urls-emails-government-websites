from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import approx

from backend.app.main import app


client = TestClient(app)


def test_health_and_feature_manifest() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["feature_list_ok"] is True


def test_government_url_is_not_inverted() -> None:
    response = client.post("/v1/url/check", json={"url": "https://uidai.gov.in/en/my-aadhaar"})
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "LEGIT"
    assert body["risk_level"] == "LOW"
    assert body["evidence"]["gov"] == "LEGIT_GOV"


def test_known_lookalike_is_high_risk() -> None:
    response = client.post(
        "/v1/url/check",
        json={"url": "https://uidai-aadhar-update.xyz/login"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] in {"PHISHING", "SUSPICIOUS"}
    assert body["risk_level"] in {"MEDIUM", "HIGH"}


def test_email_endpoint_returns_score() -> None:
    response = client.post(
        "/v1/email/check",
        json={"subject": "verify account", "body": "click https://example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["risk_score"] <= 100
    assert body["scores"]["email"] == approx(body["risk_score"], abs=0.001)
