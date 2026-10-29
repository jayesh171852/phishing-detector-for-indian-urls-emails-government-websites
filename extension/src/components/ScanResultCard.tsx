// ============================================================
// ScanResultCard — full URL scan result display
// ============================================================

import React, { useState } from "react"
import type { ScanResult } from "~types"
import { RiskMeter } from "./RiskMeter"
import { StatusBadge } from "./StatusBadge"
import { ShapChart } from "./ShapChart"
import { getRiskConfig, extractDomain, confidenceToPercent } from "~utils/helpers"

interface ScanResultCardProps {
  result: ScanResult
}

export function ScanResultCard({ result }: ScanResultCardProps) {
  const [showShap, setShowShap] = useState(false)
  const [showGov, setShowGov] = useState(false)

  const urlResult = result.urlResult
  const govResult = result.govResult || urlResult?.gov_verification

  if (!urlResult) {
    return (
      <div style={styles.errorCard}>
        <span style={{ fontSize: 20 }}>⚠️</span>
        <div>
          <div style={{ color: "#fbbf24", fontWeight: 600, fontSize: 13 }}>
            Scan Failed
          </div>
          <div style={{ color: "#64748b", fontSize: 11, marginTop: 2 }}>
            {result.error || "Could not reach backend. Is it running?"}
          </div>
        </div>
      </div>
    )
  }

  const cfg = getRiskConfig(urlResult.risk_level)
  const domain = extractDomain(result.url || "")

  return (
    <div style={styles.card}>
      {/* Header row */}
      <div style={styles.header}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={styles.domain} title={result.url}>
            {domain}
          </div>
          <div style={styles.urlSmall} title={result.url}>
            {result.url?.slice(0, 52)}
            {(result.url?.length || 0) > 52 ? "…" : ""}
          </div>
        </div>
        <RiskMeter
          riskLevel={urlResult.risk_level}
          confidence={urlResult.confidence}
          size={80}
          strokeWidth={7}
        />
      </div>

      {/* Prediction badge */}
      <div style={styles.row}>
        <StatusBadge label={urlResult.prediction} />
        <span style={{ color: "#64748b", fontSize: 11 }}>
          {confidenceToPercent(urlResult.confidence)} confidence
        </span>
        <span style={{ color: "#64748b", fontSize: 11 }}>
          {urlResult.processing_time_ms}ms
        </span>
      </div>

      {/* Message */}
      <div style={styles.message(urlResult.risk_level)}>
        {urlResult.message}
      </div>

      {/* Feature highlights */}
      {urlResult.features && (
        <div style={styles.featureGrid}>
          <FeaturePill
            label="HTTPS"
            value={urlResult.features.is_https ? "Yes" : "No"}
            good={urlResult.features.is_https === 1}
          />
          <FeaturePill
            label="Suspicious KW"
            value={urlResult.features.has_suspicious_keywords ? "Yes" : "No"}
            good={urlResult.features.has_suspicious_keywords === 0}
          />
          <FeaturePill
            label="IP Address"
            value={urlResult.features.has_ip_address ? "Yes" : "No"}
            good={urlResult.features.has_ip_address === 0}
          />
          <FeaturePill
            label="URL Length"
            value={String(urlResult.features.url_length)}
            good={urlResult.features.url_length < 75}
          />
          <FeaturePill
            label="Entropy"
            value={urlResult.features.entropy.toFixed(2)}
            good={urlResult.features.entropy < 4}
          />
          <FeaturePill
            label="Subdomains"
            value={String(urlResult.features.num_subdomains)}
            good={urlResult.features.num_subdomains <= 1}
          />
        </div>
      )}

      {/* Government verification section */}
      {govResult && govResult.status !== "not_government" && (
        <div style={styles.section}>
          <button
            style={styles.sectionToggle}
            onClick={() => setShowGov(!showGov)}
          >
            <span>🏛️ Government Verification</span>
            <StatusBadge label={govResult.status} variant="gov" />
            <span style={{ marginLeft: "auto", color: "#64748b" }}>
              {showGov ? "▲" : "▼"}
            </span>
          </button>
          {showGov && (
            <div style={styles.sectionBody}>
              <p style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.5 }}>
                {govResult.explanation}
              </p>
              {govResult.similar_domains.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={styles.subLabel}>Similar Official Domains</div>
                  {govResult.similar_domains.slice(0, 3).map((sd, i) => (
                    <div key={i} style={styles.similarRow}>
                      <span style={{ color: "#60a5fa" }}>{sd.domain}</span>
                      <span style={{ color: "#64748b" }}>{sd.department}</span>
                      <span style={{ color: "#fbbf24" }}>
                        {Math.round(sd.similarity_score * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* SHAP Explanation */}
      {urlResult.shap_explanation && (
        <div style={styles.section}>
          <button
            style={styles.sectionToggle}
            onClick={() => setShowShap(!showShap)}
          >
            <span>🔬 AI Explanation (SHAP)</span>
            <span style={{ marginLeft: "auto", color: "#64748b" }}>
              {showShap ? "▲" : "▼"}
            </span>
          </button>
          {showShap && (
            <div style={styles.sectionBody}>
              <ShapChart explanation={urlResult.shap_explanation} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FeaturePill({
  label,
  value,
  good,
}: {
  label: string
  value: string
  good: boolean
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "5px 8px",
        borderRadius: 6,
        background: good
          ? "rgba(34,197,94,0.07)"
          : "rgba(239,68,68,0.07)",
        border: `1px solid ${good ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
        minWidth: 62,
      }}
    >
      <span
        style={{
          color: good ? "#4ade80" : "#f87171",
          fontSize: 12,
          fontWeight: 700,
        }}
      >
        {value}
      </span>
      <span style={{ color: "#64748b", fontSize: 9, marginTop: 1 }}>{label}</span>
    </div>
  )
}

// ─── Styles ───────────────────────────────────────────────────

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
    gap: 12,
  },
  domain: {
    color: "#e2e8f0",
    fontWeight: 700,
    fontSize: 14,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  urlSmall: {
    color: "#475569",
    fontSize: 10,
    marginTop: 2,
    fontFamily: "monospace",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap" as const,
  },
  message: (risk: string) => ({
    fontSize: 12,
    color:
      risk === "critical" || risk === "high"
        ? "#fca5a5"
        : risk === "medium"
        ? "#fde68a"
        : "#86efac",
    lineHeight: 1.5,
    padding: "6px 10px",
    borderRadius: 6,
    background:
      risk === "critical" || risk === "high"
        ? "rgba(239,68,68,0.06)"
        : risk === "medium"
        ? "rgba(251,191,36,0.06)"
        : "rgba(34,197,94,0.06)",
    border: `1px solid ${
      risk === "critical" || risk === "high"
        ? "rgba(239,68,68,0.15)"
        : risk === "medium"
        ? "rgba(251,191,36,0.15)"
        : "rgba(34,197,94,0.15)"
    }`,
  }),
  featureGrid: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 6,
  },
  section: {
    borderRadius: 8,
    overflow: "hidden",
    border: "1px solid #1e293b",
  },
  sectionToggle: {
    width: "100%",
    background: "#0f1929",
    border: "none",
    padding: "8px 12px",
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "#94a3b8",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    textAlign: "left" as const,
  },
  sectionBody: {
    padding: "10px 12px",
    background: "#080f1d",
  },
  subLabel: {
    color: "#64748b",
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    marginBottom: 4,
  },
  similarRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 11,
    padding: "3px 0",
    borderBottom: "1px solid #0f172a",
  },
  errorCard: {
    background: "rgba(251,191,36,0.05)",
    border: "1px solid rgba(251,191,36,0.2)",
    borderRadius: 10,
    padding: 12,
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
  },
}
