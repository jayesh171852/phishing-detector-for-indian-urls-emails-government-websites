// ============================================================
// AI-GovShield — Shared TypeScript Types
// ============================================================

// ─── Enums ───────────────────────────────────────────────────

export type RiskLevel = "safe" | "low" | "medium" | "high" | "critical"

export type PredictionLabel = "legitimate" | "phishing" | "suspicious" | "unknown"

export type GovVerificationStatus =
  | "official"
  | "fake"
  | "impersonating"
  | "not_government"
  | "unknown"

export type ScanType = "url" | "email" | "government"

export type TabStatus = "idle" | "scanning" | "complete" | "error"

// ─── SHAP Explainability ────────────────────────────────────

export interface FeatureContribution {
  feature: string
  value: number
  contribution: number
  impact: "positive" | "negative"
  description: string
}

export interface ShapExplanation {
  top_features: FeatureContribution[]
  base_value: number
  prediction_value: number
  summary: string
}

// ─── URL Prediction ─────────────────────────────────────────

export interface URLFeatures {
  url_length: number
  hostname_length: number
  path_length: number
  domain_length: number
  is_https: number
  num_dots: number
  num_digits: number
  num_hyphens: number
  num_subdomains: number
  entropy: number
  tld: string
  has_ip_address: number
  num_special_chars: number
  is_url_shortener: number
  has_suspicious_keywords: number
  gov_domain_similarity: number
  has_at_symbol: number
  has_double_slash: number
  path_depth: number
  query_length: number
  has_port: number
  domain_age_days: number
  has_valid_ssl: number
}

export interface URLPredictionRequest {
  url: string
  include_shap?: boolean
  include_gov_check?: boolean
}

export interface URLPredictionResponse {
  success: boolean
  url: string
  prediction: PredictionLabel
  confidence: number
  risk_level: RiskLevel
  is_phishing: boolean
  features?: URLFeatures
  shap_explanation?: ShapExplanation
  gov_verification?: GovVerificationResponse
  processing_time_ms: number
  message: string
}

// ─── Email Prediction ────────────────────────────────────────

export interface EmailPredictionRequest {
  subject: string
  body: string
  sender?: string
}

export interface EmailPredictionResponse {
  success: boolean
  prediction: PredictionLabel
  confidence: number
  risk_level: RiskLevel
  is_phishing: boolean
  suspicious_indicators: string[]
  processing_time_ms: number
  message: string
}

// ─── Government Verification ─────────────────────────────────

export interface SimilarGovDomain {
  domain: string
  similarity_score: number
  match_type: string
  department: string
}

export interface GovVerificationResponse {
  success: boolean
  url: string
  status: GovVerificationStatus
  is_official: boolean
  is_impersonating: boolean
  matched_domain?: string
  similar_domains: SimilarGovDomain[]
  impersonation_score: number
  risk_level: RiskLevel
  explanation: string
  processing_time_ms: number
}

// ─── SHAP Explain ────────────────────────────────────────────

export interface ExplainResponse {
  success: boolean
  url: string
  prediction: PredictionLabel
  confidence: number
  shap_explanation: ShapExplanation
  processing_time_ms: number
}

// ─── Health ──────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  version: string
  models: Record<string, boolean>
  uptime_seconds: number
}

// ─── Extension Internal ──────────────────────────────────────

export interface ScanResult {
  id: string
  type: ScanType
  url?: string
  emailSubject?: string
  timestamp: number
  urlResult?: URLPredictionResponse
  emailResult?: EmailPredictionResponse
  govResult?: GovVerificationResponse
  error?: string
}

export interface ExtensionSettings {
  apiBaseUrl: string
  autoScanOnLoad: boolean
  showNotifications: boolean
  includeShap: boolean
  enableGovCheck: boolean
  enableEmailScan: boolean
  darkMode: boolean
}

export interface ExtensionStorage {
  settings: ExtensionSettings
  history: ScanResult[]
  lastScanResult?: ScanResult
}

// ─── Messages (content ↔ background ↔ popup) ────────────────

export type MessageType =
  | "SCAN_URL"
  | "SCAN_EMAIL"
  | "SCAN_RESULT"
  | "TAB_CHANGED"
  | "GET_STATUS"
  | "GET_HISTORY"
  | "CLEAR_HISTORY"
  | "SETTINGS_UPDATED"
  | "EMAIL_DETECTED"
  | "API_ERROR"

export interface ExtensionMessage {
  type: MessageType
  payload?: unknown
}

export interface ScanUrlMessage extends ExtensionMessage {
  type: "SCAN_URL"
  payload: { url: string }
}

export interface ScanEmailMessage extends ExtensionMessage {
  type: "SCAN_EMAIL"
  payload: EmailPredictionRequest
}

export interface ScanResultMessage extends ExtensionMessage {
  type: "SCAN_RESULT"
  payload: ScanResult
}

export interface EmailDetectedMessage extends ExtensionMessage {
  type: "EMAIL_DETECTED"
  payload: EmailPredictionRequest
}

// ─── UI State ────────────────────────────────────────────────

export interface PopupState {
  tabStatus: TabStatus
  currentUrl: string
  currentTab: "scanner" | "email" | "history" | "settings"
  scanResult?: ScanResult
  isLoading: boolean
  apiOnline: boolean
  error?: string
}
