// ============================================================
// AI-GovShield — Utility Helpers
// ============================================================

import type { RiskLevel, PredictionLabel, ScanResult, ExtensionSettings } from "~types"

// ─── Risk Level Helpers ───────────────────────────────────────

export const RISK_CONFIG: Record<
  RiskLevel,
  { label: string; color: string; bgColor: string; icon: string; hex: string }
> = {
  safe: {
    label: "Safe",
    color: "text-emerald-400",
    bgColor: "bg-emerald-400/10 border-emerald-400/30",
    icon: "shield-check",
    hex: "#34d399",
  },
  low: {
    label: "Low Risk",
    color: "text-blue-400",
    bgColor: "bg-blue-400/10 border-blue-400/30",
    icon: "shield",
    hex: "#60a5fa",
  },
  medium: {
    label: "Medium Risk",
    color: "text-amber-400",
    bgColor: "bg-amber-400/10 border-amber-400/30",
    icon: "alert-triangle",
    hex: "#fbbf24",
  },
  high: {
    label: "High Risk",
    color: "text-orange-400",
    bgColor: "bg-orange-400/10 border-orange-400/30",
    icon: "alert-octagon",
    hex: "#fb923c",
  },
  critical: {
    label: "Critical",
    color: "text-red-400",
    bgColor: "bg-red-400/10 border-red-400/30",
    icon: "skull",
    hex: "#f87171",
  },
}

export function getRiskConfig(level: RiskLevel) {
  return RISK_CONFIG[level] ?? RISK_CONFIG.low
}

export function confidenceToPercent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

export function confidenceToBar(confidence: number): number {
  return Math.round(confidence * 100)
}

// ─── Domain Extraction ────────────────────────────────────────

export function extractDomain(url: string): string {
  try {
    const u = new URL(url.startsWith("http") ? url : `https://${url}`)
    return u.hostname
  } catch {
    return url
  }
}

export function truncateUrl(url: string, maxLen = 48): string {
  if (url.length <= maxLen) return url
  const domain = extractDomain(url)
  if (domain.length < maxLen - 3) return domain + "…"
  return url.slice(0, maxLen - 3) + "…"
}

export function isGovUrl(url: string): boolean {
  const domain = extractDomain(url).toLowerCase()
  return (
    domain.endsWith(".gov.in") ||
    domain.endsWith(".nic.in") ||
    domain.endsWith(".gov") ||
    domain.endsWith(".edu.in")
  )
}

// ─── History Storage Helpers ─────────────────────────────────

export async function saveToHistory(result: ScanResult): Promise<void> {
  const { history = [] } = await chrome.storage.local.get("history")
  const updated = [result, ...history].slice(0, 50) // keep last 50
  await chrome.storage.local.set({ history: updated, lastScanResult: result })
}

export async function getHistory(): Promise<ScanResult[]> {
  const { history = [] } = await chrome.storage.local.get("history")
  return history as ScanResult[]
}

export async function clearHistory(): Promise<void> {
  await chrome.storage.local.set({ history: [], lastScanResult: undefined })
}

// ─── Settings Helpers ─────────────────────────────────────────

export const DEFAULT_SETTINGS: ExtensionSettings = {
  apiBaseUrl: "http://localhost:8000",
  autoScanOnLoad: true,
  showNotifications: true,
  includeShap: true,
  enableGovCheck: true,
  enableEmailScan: true,
  darkMode: true,
}

export async function getSettings(): Promise<ExtensionSettings> {
  const { settings } = await chrome.storage.local.get("settings")
  return { ...DEFAULT_SETTINGS, ...(settings ?? {}) }
}

export async function saveSettings(
  partial: Partial<ExtensionSettings>
): Promise<ExtensionSettings> {
  const current = await getSettings()
  const updated = { ...current, ...partial }
  await chrome.storage.local.set({ settings: updated })
  return updated
}

// ─── Scan Result Factory ─────────────────────────────────────

export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

// ─── Date Helpers ─────────────────────────────────────────────

export function formatTimestamp(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

// ─── Notification Helper ──────────────────────────────────────

export function showNotification(
  title: string,
  message: string,
  riskLevel: RiskLevel = "low"
): void {
  const iconMap: Record<RiskLevel, string> = {
    safe: "icons/icon-safe.png",
    low: "icons/icon-safe.png",
    medium: "icons/icon-warn.png",
    high: "icons/icon-danger.png",
    critical: "icons/icon-danger.png",
  }

  chrome.notifications?.create({
    type: "basic",
    iconUrl: iconMap[riskLevel] || "icons/icon128.png",
    title,
    message,
    priority: riskLevel === "critical" || riskLevel === "high" ? 2 : 0,
  })
}
