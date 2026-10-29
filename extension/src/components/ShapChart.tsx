// ============================================================
// ShapChart — SHAP feature importance horizontal bar chart
// ============================================================

import React, { useState } from "react"
import type { ShapExplanation, FeatureContribution } from "~types"

interface ShapChartProps {
  explanation: ShapExplanation
}

export function ShapChart({ explanation }: ShapChartProps) {
  const [expanded, setExpanded] = useState(false)

  const features = explanation.top_features
  if (!features || features.length === 0) {
    return (
      <div style={{ color: "#64748b", fontSize: 12, padding: "8px 0" }}>
        No SHAP explanation available.
      </div>
    )
  }

  // Normalise bar widths by absolute max contribution
  const maxAbs = Math.max(...features.map((f) => Math.abs(f.contribution)), 0.001)

  const visible = expanded ? features : features.slice(0, 5)

  return (
    <div>
      {/* Summary */}
      {explanation.summary && (
        <p
          style={{
            color: "#94a3b8",
            fontSize: 11,
            lineHeight: 1.5,
            marginBottom: 10,
            borderLeft: "2px solid #1e40af",
            paddingLeft: 8,
          }}
        >
          {explanation.summary}
        </p>
      )}

      {/* Feature bars */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {visible.map((feat, i) => (
          <FeatureBar key={i} feature={feat} maxAbs={maxAbs} />
        ))}
      </div>

      {features.length > 5 && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: 8,
            background: "transparent",
            border: "1px solid #1e293b",
            borderRadius: 6,
            color: "#60a5fa",
            fontSize: 11,
            padding: "4px 10px",
            cursor: "pointer",
            width: "100%",
          }}
        >
          {expanded ? "Show less" : `Show all ${features.length} features`}
        </button>
      )}
    </div>
  )
}

function FeatureBar({
  feature,
  maxAbs,
}: {
  feature: FeatureContribution
  maxAbs: number
}) {
  const pct = Math.round((Math.abs(feature.contribution) / maxAbs) * 100)
  const isPositive = feature.impact === "positive"
  const barColor = isPositive ? "#f87171" : "#34d399"
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: "relative" }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 2,
        }}
      >
        {/* Feature name */}
        <span
          style={{
            color: "#cbd5e1",
            fontSize: 11,
            minWidth: 120,
            maxWidth: 120,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={feature.description}
        >
          {feature.feature.replace(/_/g, " ")}
        </span>

        {/* Bar */}
        <div
          style={{
            flex: 1,
            height: 12,
            background: "#0f172a",
            borderRadius: 4,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${pct}%`,
              background: barColor,
              borderRadius: 4,
              transition: "width 0.6s ease",
              opacity: 0.85,
            }}
          />
        </div>

        {/* Score */}
        <span
          style={{
            color: barColor,
            fontSize: 10,
            minWidth: 36,
            textAlign: "right",
            fontFamily: "monospace",
          }}
        >
          {isPositive ? "+" : ""}
          {(feature.contribution * 100).toFixed(1)}%
        </span>
      </div>

      {/* Hover tooltip */}
      {hovered && (
        <div
          style={{
            position: "absolute",
            bottom: "100%",
            left: 0,
            right: 0,
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 6,
            padding: "6px 8px",
            fontSize: 11,
            color: "#e2e8f0",
            zIndex: 100,
            pointerEvents: "none",
            marginBottom: 4,
          }}
        >
          <strong>{feature.feature}</strong>: {feature.description}
          <br />
          Value: <code>{feature.value}</code>
        </div>
      )}
    </div>
  )
}
