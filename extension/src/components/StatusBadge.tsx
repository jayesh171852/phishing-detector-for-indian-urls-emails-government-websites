// ============================================================
// StatusBadge — inline prediction label badge
// ============================================================

import React from "react"
import type { PredictionLabel, RiskLevel } from "~types"

interface StatusBadgeProps {
  label: PredictionLabel | RiskLevel | string
  variant?: "prediction" | "risk" | "gov"
}

const PREDICTION_STYLES: Record<string, React.CSSProperties> = {
  phishing: {
    background: "rgba(239,68,68,0.12)",
    border: "1px solid rgba(239,68,68,0.4)",
    color: "#f87171",
  },
  suspicious: {
    background: "rgba(251,191,36,0.12)",
    border: "1px solid rgba(251,191,36,0.4)",
    color: "#fbbf24",
  },
  legitimate: {
    background: "rgba(34,197,94,0.12)",
    border: "1px solid rgba(34,197,94,0.4)",
    color: "#4ade80",
  },
  unknown: {
    background: "rgba(100,116,139,0.12)",
    border: "1px solid rgba(100,116,139,0.4)",
    color: "#94a3b8",
  },
  // gov statuses
  official: {
    background: "rgba(34,197,94,0.12)",
    border: "1px solid rgba(34,197,94,0.4)",
    color: "#4ade80",
  },
  fake: {
    background: "rgba(239,68,68,0.12)",
    border: "1px solid rgba(239,68,68,0.4)",
    color: "#f87171",
  },
  impersonating: {
    background: "rgba(239,68,68,0.15)",
    border: "1px solid rgba(239,68,68,0.5)",
    color: "#f87171",
  },
  not_government: {
    background: "rgba(100,116,139,0.12)",
    border: "1px solid rgba(100,116,139,0.3)",
    color: "#94a3b8",
  },
}

const LABEL_TEXT: Record<string, string> = {
  phishing: "PHISHING",
  suspicious: "SUSPICIOUS",
  legitimate: "LEGITIMATE",
  unknown: "UNKNOWN",
  official: "OFFICIAL",
  fake: "FAKE GOVT SITE",
  impersonating: "IMPERSONATING",
  not_government: "NOT GOVT",
  safe: "SAFE",
  low: "LOW RISK",
  medium: "MEDIUM RISK",
  high: "HIGH RISK",
  critical: "CRITICAL",
}

const LABEL_ICONS: Record<string, string> = {
  phishing: "🚨",
  suspicious: "⚠️",
  legitimate: "✅",
  official: "🏛️",
  fake: "🚫",
  impersonating: "🎭",
  safe: "✅",
  critical: "🔴",
  high: "🟠",
  medium: "🟡",
  low: "🔵",
}

export function StatusBadge({ label, variant = "prediction" }: StatusBadgeProps) {
  const key = label?.toLowerCase?.() || "unknown"
  const style = PREDICTION_STYLES[key] ?? PREDICTION_STYLES.unknown
  const text = LABEL_TEXT[key] ?? label.toUpperCase()
  const icon = LABEL_ICONS[key] ?? ""

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.5px",
        ...style,
      }}
    >
      {icon && <span style={{ fontSize: 11 }}>{icon}</span>}
      {text}
    </span>
  )
}
