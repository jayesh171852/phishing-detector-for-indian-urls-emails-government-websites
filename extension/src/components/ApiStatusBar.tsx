// ============================================================
// ApiStatusBar — top bar showing backend connection status
// ============================================================

import React from "react"

interface ApiStatusBarProps {
  online: boolean
  checking: boolean
  modelStatus?: Record<string, boolean>
}

export function ApiStatusBar({
  online,
  checking,
  modelStatus,
}: ApiStatusBarProps) {
  const loadedCount = modelStatus
    ? Object.values(modelStatus).filter(Boolean).length
    : 0
  const totalCount = modelStatus ? Object.keys(modelStatus).length : 0

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 8px",
        borderRadius: 6,
        background: checking
          ? "rgba(99,102,241,0.08)"
          : online
          ? "rgba(34,197,94,0.08)"
          : "rgba(239,68,68,0.08)",
        border: `1px solid ${
          checking
            ? "rgba(99,102,241,0.25)"
            : online
            ? "rgba(34,197,94,0.25)"
            : "rgba(239,68,68,0.25)"
        }`,
        fontSize: 10,
      }}
    >
      {/* Pulse dot */}
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: checking ? "#818cf8" : online ? "#4ade80" : "#f87171",
          animation: checking ? "gs-pulse 1s infinite" : undefined,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          color: checking ? "#818cf8" : online ? "#4ade80" : "#f87171",
          fontWeight: 600,
        }}
      >
        {checking
          ? "Connecting…"
          : online
          ? `Backend Online`
          : "Backend Offline"}
      </span>
      {online && modelStatus && (
        <span style={{ color: "#64748b", marginLeft: 2 }}>
          · {loadedCount}/{totalCount} models
        </span>
      )}
    </div>
  )
}
