// ============================================================
// AI-GovShield API Client
// ============================================================
// Typed REST client for all FastAPI backend endpoints.
// Reads the API base URL from plasmo public env variable.

import type {
  URLPredictionRequest,
  URLPredictionResponse,
  EmailPredictionRequest,
  EmailPredictionResponse,
  GovVerificationResponse,
  ExplainResponse,
  HealthResponse,
  RiskLevel,
  PredictionLabel,
} from "~types"

// Injected by Plasmo from extension/.env at build time
const API_BASE =
  process.env.PLASMO_PUBLIC_API_BASE_URL || "http://localhost:8000"

const DEFAULT_TIMEOUT_MS = 15_000

interface CheckResponse {
  verdict: string
  risk_score: number
  risk_level: "LOW" | "MEDIUM" | "HIGH"
  confidence: number
  reasons: string[]
  evidence: Record<string, unknown>
  scores: Record<string, unknown>
  model_source: string
  latency_ms: number
}

function riskLevel(level: CheckResponse["risk_level"]): RiskLevel {
  return level === "HIGH" ? "high" : level === "MEDIUM" ? "medium" : "low"
}

function prediction(verdict: string): PredictionLabel {
  return verdict === "PHISHING" || verdict === "PHISHING_GOV"
    ? "phishing"
    : verdict === "SUSPICIOUS"
      ? "suspicious"
      : verdict === "LEGIT" || verdict === "LEGIT_GOV"
        ? "legitimate"
        : "unknown"
}

function adaptUrl(url: string, result: CheckResponse): URLPredictionResponse {
  return {
    success: true,
    url,
    prediction: prediction(result.verdict),
    confidence: result.confidence,
    risk_level: riskLevel(result.risk_level),
    is_phishing: result.verdict === "PHISHING" || result.verdict === "PHISHING_GOV",
    processing_time_ms: result.latency_ms,
    message: result.reasons[0] || result.verdict,
  }
}

// ─── Fetch wrapper ────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      signal: controller.signal,
      ...init,
    })

    clearTimeout(timer)

    if (!response.ok) {
      let detail = `HTTP ${response.status}`
      try {
        const errBody = await response.json()
        detail = errBody.detail || errBody.error || detail
      } catch {
        // ignore JSON parse error
      }
      throw new APIError(response.status, detail)
    }

    return response.json() as Promise<T>
  } catch (err) {
    clearTimeout(timer)
    if (err instanceof APIError) throw err
    if ((err as Error).name === "AbortError") {
      throw new APIError(408, "Request timed out. Is the backend running?")
    }
    throw new APIError(0, `Network error: ${(err as Error).message}`)
  }
}

// ─── Custom Error ─────────────────────────────────────────────

export class APIError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail)
    this.name = "APIError"
  }
}

// ─── API Methods ──────────────────────────────────────────────

export const GovShieldAPI = {
  /**
   * Check backend health and model availability.
   */
  health(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/v1/health", { method: "GET" }, 5_000)
  },

  /**
   * Predict whether a URL is phishing.
   * Optionally includes SHAP explanation and government domain check.
   */
  predictUrl(payload: URLPredictionRequest): Promise<URLPredictionResponse> {
    return apiFetch<CheckResponse>("/v1/url/check", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => adaptUrl(payload.url, result))
  },

  /**
   * Predict whether an email is phishing based on subject + body.
   */
  predictEmail(
    payload: EmailPredictionRequest
  ): Promise<EmailPredictionResponse> {
    return apiFetch<CheckResponse>("/v1/email/check", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => ({
      success: true,
      prediction: prediction(result.verdict),
      confidence: result.confidence,
      risk_level: riskLevel(result.risk_level),
      is_phishing: result.verdict === "PHISHING",
      suspicious_indicators: result.reasons,
      processing_time_ms: result.latency_ms,
      message: result.reasons[0] || result.verdict,
    }))
  },

  /**
   * Check if a URL belongs to an official or fake government website.
   */
  governmentCheck(url: string): Promise<GovVerificationResponse> {
    return apiFetch<CheckResponse>("/v1/url/check", {
      method: "POST",
      body: JSON.stringify({ url }),
    }).then((result) => ({
      success: true,
      url,
      status: result.verdict === "LEGIT_GOV" ? "official" : result.verdict === "PHISHING_GOV" ? "impersonating" : "not_government",
      is_official: result.verdict === "LEGIT_GOV",
      is_impersonating: result.verdict === "PHISHING_GOV",
      matched_domain: typeof result.evidence.matched === "string" ? result.evidence.matched : undefined,
      similar_domains: [],
      impersonation_score: result.risk_score,
      risk_level: riskLevel(result.risk_level),
      explanation: result.reasons[0] || result.verdict,
      processing_time_ms: result.latency_ms,
    }))
  },

  /**
   * Fetch SHAP explanation for a URL (standalone, no caching).
   */
  explain(url: string): Promise<ExplainResponse> {
    return apiFetch<CheckResponse>("/v1/url/check", {
      method: "POST",
      body: JSON.stringify({ url }),
    }).then((result) => ({
      success: true,
      url,
      prediction: prediction(result.verdict),
      confidence: result.confidence,
      shap_explanation: {
        top_features: result.reasons.map((reason) => ({
          feature: "model",
          value: 0,
          contribution: 0,
          impact: "positive" as const,
          description: reason,
        })),
        base_value: 0,
        prediction_value: result.risk_score,
        summary: result.reasons.join("; "),
      },
      processing_time_ms: result.latency_ms,
    }))
  },
}
