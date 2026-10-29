// ============================================================
// EmailResultCard — email phishing result display
// ============================================================

import React from "react"
import type { ScanResult } from "~types"
import { StatusBadge } from "./StatusBadge"
import { RiskMeter } from "./RiskMeter"
import { confidenceToPercent } from "~utils/helpers"

interface EmailResultCardProps {
  result: ScanResult
}

export function EmailResultCard({ result }: EmailResultCardProps) {
  const emailResult = result.emailResult

  if (!emailResult) {
    return (
      <div style={styles.errorCard}>
        <span style={{ fontSize: 18 }}>⚠️</span>
        <div style={{ color: "#fbbf24", fontSize: 12 }}>
          {result.error || "Email scan failed."}
        </div>
      </div>
    )
  }

  const isPhishing = emailResult.is_phishing

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.header}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={styles.subject} title={result.emailSubject}>
            📧 {result.emailSubject?.slice(0, 50) || "Email Analysis"}
          </div>
          <div style={styles.row}>
            <StatusBadge label={emailResult.prediction} />
            <span style={{ color: "#64748b", fontSize: 11 }}>
              {confidenceToPercent(emailResult.confidence)}
            </span>
          </div>
        </div>
        <RiskMeter
          riskLevel={emailResult.risk_level}
          confidence={emailResult.confidence}
          size={76}
          strokeWidth={6}
        />
      </div>

      {/* Message */}
      <div
        style={{
          fontSize: 12,
          color: isPhishing ? "#fca5a5" : "#86efac",
          lineHeight: 1.5,
          padding: "6px 10px",
          borderRadius: 6,
          background: isPhishing
            ? "rgba(239,68,68,0.06)"
            : "rgba(34,197,94,0.06)",
          border: `1px solid ${
            isPhishing ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)"
          }`,
        }}
      >
        {emailResult.message}
      </div>

      {/* Suspicious indicators */}
      {emailResult.suspicious_indicators.length > 0 && (
        <div>
          <div style={styles.subLabel}>Suspicious Indicators</div>
          <div style={styles.indicatorList}>
            {emailResult.suspicious_indicators.map((ind, i) => (
              <div key={i} style={styles.indicator}>
                <span style={{ color: "#f87171", fontSize: 11 }}>⚠</span>
                <span style={{ color: "#fca5a5", fontSize: 11 }}>{ind}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Processing time */}
      <div style={{ color: "#334155", fontSize: 10, textAlign: "right" as const }}>
        Analysed in {emailResult.processing_time_ms}ms
      </div>
    </div>
  )
}

const styles = {
  card: {
    background: "#0d1526",
    borderRadius: 12,
    padding: 14,
    border: "1px solid #1e293b",
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
  },
  subject: {
    color: "#e2e8f0",
    fontWeight: 600,
    fontSize: 13,
    marginBottom: 6,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  subLabel: {
    color: "#64748b",
    fontSize: 10,
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    marginBottom: 6,
  },
  indicatorList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    maxHeight: 120,
    overflowY: "auto" as const,
  },
  indicator: {
    display: "flex",
    alignItems: "flex-start",
    gap: 6,
    padding: "4px 8px",
    borderRadius: 4,
    background: "rgba(239,68,68,0.05)",
    border: "1px solid rgba(239,68,68,0.1)",
  },
  errorCard: {
    background: "rgba(251,191,36,0.05)",
    border: "1px solid rgba(251,191,36,0.2)",
    borderRadius: 10,
    padding: 12,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
}
