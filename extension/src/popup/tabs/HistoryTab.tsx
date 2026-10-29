// ============================================================
// HistoryTab — scan history with risk badges
// ============================================================

import React, { useState } from "react"
import { useHistory } from "~hooks/useHistory"
import { StatusBadge } from "~components/StatusBadge"
import { extractDomain, formatTimestamp, getRiskConfig } from "~utils/helpers"
import type { ScanResult } from "~types"

export function HistoryTab() {
  const { history, loading, reload, clear } = useHistory()
  const [confirmClear, setConfirmClear] = useState(false)

  const handleClear = async () => {
    if (!confirmClear) {
      setConfirmClear(true)
      setTimeout(() => setConfirmClear(false), 3000)
      return
    }
    await clear()
    setConfirmClear(false)
  }

  if (loading) {
    return (
      <div style={styles.center}>
        <span style={styles.spinner} />
        <span style={{ color: "#64748b", fontSize: 12 }}>Loading history…</span>
      </div>
    )
  }

  if (history.length === 0) {
    return (
      <div style={styles.empty}>
        <span style={{ fontSize: 32 }}>📋</span>
        <span style={{ color: "#64748b", fontSize: 13 }}>
          No scans yet. Browse the web to start detecting threats.
        </span>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {/* Header row */}
      <div style={styles.headerRow}>
        <span style={{ color: "#64748b", fontSize: 11 }}>
          {history.length} scan{history.length !== 1 ? "s" : ""}
        </span>
        <button
          onClick={handleClear}
          style={{
            ...styles.clearBtn,
            color: confirmClear ? "#f87171" : "#64748b",
            borderColor: confirmClear ? "rgba(239,68,68,0.4)" : "#1e293b",
          }}
        >
          {confirmClear ? "Confirm Clear?" : "Clear History"}
        </button>
      </div>

      {/* History list */}
      <div style={styles.list}>
        {history.map((item) => (
          <HistoryItem key={item.id} item={item} />
        ))}
      </div>
    </div>
  )
}

function HistoryItem({ item }: { item: ScanResult }) {
  const [expanded, setExpanded] = useState(false)

  const isUrl = item.type === "url" || item.type === "government"
  const isEmail = item.type === "email"

  const risk = isUrl
    ? item.urlResult?.risk_level || "low"
    : item.emailResult?.risk_level || "low"
  const isPhishing = isUrl
    ? item.urlResult?.is_phishing
    : item.emailResult?.is_phishing
  const cfg = getRiskConfig(risk as any)
  const title = isUrl
    ? extractDomain(item.url || "")
    : item.emailSubject?.slice(0, 40) || "Email"

  return (
    <div
      style={{
        ...styles.item,
        borderLeftColor: cfg.hex,
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={styles.itemHeader}>
        <span style={{ fontSize: 14 }}>{isEmail ? "📧" : "🌐"}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={styles.itemTitle} title={item.url || item.emailSubject}>
            {title}
          </div>
          <div style={styles.itemTime}>{formatTimestamp(item.timestamp)}</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
          {isPhishing !== undefined && (
            <StatusBadge
              label={isPhishing ? "phishing" : "legitimate"}
            />
          )}
          {item.error && <StatusBadge label="unknown" />}
        </div>
      </div>

      {expanded && (
        <div style={styles.itemDetails}>
          {item.url && (
            <div style={styles.detailRow}>
              <span style={styles.detailKey}>URL</span>
              <span style={styles.detailVal}>{item.url.slice(0, 60)}</span>
            </div>
          )}
          {isUrl && item.urlResult && (
            <>
              <div style={styles.detailRow}>
                <span style={styles.detailKey}>Confidence</span>
                <span style={{ color: cfg.hex, fontSize: 11 }}>
                  {Math.round((item.urlResult.confidence ?? 0) * 100)}%
                </span>
              </div>
              <div style={styles.detailRow}>
                <span style={styles.detailKey}>Risk</span>
                <span style={{ color: cfg.hex, fontSize: 11 }}>
                  {item.urlResult.risk_level?.toUpperCase()}
                </span>
              </div>
            </>
          )}
          {isEmail && item.emailResult && (
            <>
              <div style={styles.detailRow}>
                <span style={styles.detailKey}>Confidence</span>
                <span style={{ color: cfg.hex, fontSize: 11 }}>
                  {Math.round((item.emailResult.confidence ?? 0) * 100)}%
                </span>
              </div>
              {item.emailResult.suspicious_indicators.slice(0, 2).map((ind, i) => (
                <div key={i} style={{ color: "#f87171", fontSize: 10, paddingLeft: 4 }}>
                  ⚠ {ind}
                </div>
              ))}
            </>
          )}
          {item.error && (
            <div style={{ color: "#f87171", fontSize: 11 }}>{item.error}</div>
          )}
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  clearBtn: {
    background: "transparent",
    border: "1px solid #1e293b",
    borderRadius: 6,
    padding: "3px 10px",
    fontSize: 11,
    cursor: "pointer",
    transition: "color 0.2s, border-color 0.2s",
  },
  list: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
    maxHeight: 420,
    overflowY: "auto" as const,
  },
  item: {
    background: "#0a1525",
    border: "1px solid #1e293b",
    borderLeft: "3px solid #1e293b",
    borderRadius: 8,
    padding: "8px 10px",
    cursor: "pointer",
    transition: "background 0.15s",
  },
  itemHeader: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  itemTitle: {
    color: "#cbd5e1",
    fontSize: 12,
    fontWeight: 600,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  itemTime: {
    color: "#334155",
    fontSize: 10,
    marginTop: 2,
  },
  itemDetails: {
    marginTop: 8,
    paddingTop: 8,
    borderTop: "1px solid #1e293b",
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  detailRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  detailKey: {
    color: "#475569",
    fontSize: 11,
  },
  detailVal: {
    color: "#94a3b8",
    fontSize: 10,
    fontFamily: "monospace",
    textAlign: "right" as const,
    maxWidth: 220,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  center: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    padding: "40px 0",
  },
  empty: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    padding: "40px 20px",
    textAlign: "center" as const,
  },
  spinner: {
    display: "inline-block",
    width: 20,
    height: 20,
    border: "2px solid rgba(96,165,250,0.2)",
    borderTopColor: "#60a5fa",
    borderRadius: "50%",
    animation: "gs-spin 0.7s linear infinite",
  },
}
