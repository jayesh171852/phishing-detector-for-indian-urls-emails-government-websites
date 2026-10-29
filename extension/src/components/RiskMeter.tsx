// ============================================================
// RiskMeter — Animated circular risk gauge
// ============================================================

import React from "react"
import type { RiskLevel } from "~types"
import { getRiskConfig, confidenceToBar } from "~utils/helpers"

interface RiskMeterProps {
  riskLevel: RiskLevel
  confidence: number  // 0–1
  size?: number
  strokeWidth?: number
}

export function RiskMeter({
  riskLevel,
  confidence,
  size = 100,
  strokeWidth = 8,
}: RiskMeterProps) {
  const cfg = getRiskConfig(riskLevel)
  const pct = confidenceToBar(confidence)

  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  const cx = size / 2
  const cy = size / 2

  return (
    <div className="flex flex-col items-center gap-2">
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          {/* Track */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="#1e2a3a"
            strokeWidth={strokeWidth}
          />
          {/* Progress */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={cfg.hex}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
          />
        </svg>
        {/* Center label */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span
            style={{ color: cfg.hex, fontSize: 22, fontWeight: 700, lineHeight: 1 }}
          >
            {pct}%
          </span>
          <span style={{ color: "#64748b", fontSize: 9, marginTop: 2 }}>
            CONFIDENCE
          </span>
        </div>
      </div>

      {/* Risk badge */}
      <div
        style={{
          padding: "3px 10px",
          borderRadius: 999,
          background: `${cfg.hex}18`,
          border: `1px solid ${cfg.hex}50`,
          color: cfg.hex,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.6px",
          textTransform: "uppercase",
        }}
      >
        {cfg.label}
      </div>
    </div>
  )
}
