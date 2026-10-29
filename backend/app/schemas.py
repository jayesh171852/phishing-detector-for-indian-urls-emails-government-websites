from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class URLCheckRequest(BaseModel):
    url: str = Field(min_length=1)


class EmailCheckRequest(BaseModel):
    subject: str = ""
    body: str = ""
    sender: str | None = None


class AnalyzeRequest(BaseModel):
    url: str | None = None
    subject: str | None = None
    body: str | None = None


class FeedbackRequest(BaseModel):
    url: str | None = None
    verdict: str
    correct_verdict: str | None = None
    note: str | None = None


class CheckResponse(BaseModel):
    verdict: str
    risk_score: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: float
    reasons: list[str]
    tips: list[str]
    evidence: dict[str, Any]
    scores: dict[str, Any]
    model_source: Literal["catboost", "baseline", "rule_fallback"]
    model_version: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    models: dict[str, bool]
    feature_list_ok: bool

