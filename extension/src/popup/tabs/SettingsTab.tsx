// ============================================================
// SettingsTab — extension configuration panel
// ============================================================

import React from "react"
import { useSettings } from "~hooks/useSettings"
import type { ExtensionSettings } from "~types"

export function SettingsTab() {
  const { settings, loading, update } = useSettings()

  if (loading || !settings) {
    return (
      <div style={styles.center}>
        <span style={styles.spinner} />
      </div>
    )
  }

  const toggle = (key: keyof ExtensionSettings) => {
    if (typeof settings[key] === "boolean") {
      update({ [key]: !settings[key] })
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.sectionTitle}>Backend</div>

      {/* API URL */}
      <div style={styles.field}>
        <label style={styles.label}>API Base URL</label>
        <input
          type="text"
          value={settings.apiBaseUrl}
          onChange={(e) => update({ apiBaseUrl: e.target.value })}
          style={styles.input}
          placeholder="http://localhost:8000"
        />
        <div style={styles.hint}>
          URL of the running FastAPI backend server.
        </div>
      </div>

      <div style={styles.sectionTitle}>Detection</div>

      <ToggleRow
        label="Auto-scan on page load"
        description="Automatically scan every website you visit."
        value={settings.autoScanOnLoad}
        onChange={() => toggle("autoScanOnLoad")}
      />
      <ToggleRow
        label="Government website check"
        description="Verify URLs against official Indian govt domain database."
        value={settings.enableGovCheck}
        onChange={() => toggle("enableGovCheck")}
      />
      <ToggleRow
        label="Email phishing scan"
        description="Auto-detect phishing in Gmail and Outlook."
        value={settings.enableEmailScan}
        onChange={() => toggle("enableEmailScan")}
      />
      <ToggleRow
        label="SHAP explanations"
        description="Show AI feature importance for URL predictions."
        value={settings.includeShap}
        onChange={() => toggle("includeShap")}
      />

      <div style={styles.sectionTitle}>Notifications</div>

      <ToggleRow
        label="Desktop notifications"
        description="Show Chrome notification for high-risk detections."
        value={settings.showNotifications}
        onChange={() => toggle("showNotifications")}
      />

      {/* Version */}
      <div style={styles.versionRow}>
        <span style={{ color: "#1e3a5f" }}>AI-GovShield</span>
        <span style={{ color: "#1e3a5f" }}>v1.0.0</span>
      </div>
    </div>
  )
}

function ToggleRow({
  label,
  description,
  value,
  onChange,
}: {
  label: string
  description: string
  value: boolean
  onChange: () => void
}) {
  return (
    <div style={styles.toggleRow}>
      <div style={{ flex: 1 }}>
        <div style={styles.toggleLabel}>{label}</div>
        <div style={styles.toggleDesc}>{description}</div>
      </div>
      <button
        onClick={onChange}
        role="switch"
        aria-checked={value}
        style={{
          ...styles.toggle,
          background: value
            ? "linear-gradient(135deg, #1d4ed8, #2563eb)"
            : "#1e293b",
        }}
      >
        <span
          style={{
            ...styles.toggleThumb,
            transform: value ? "translateX(18px)" : "translateX(2px)",
          }}
        />
      </button>
    </div>
  )
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  sectionTitle: {
    color: "#3b82f6",
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "1px",
    textTransform: "uppercase" as const,
    marginTop: 6,
    paddingBottom: 4,
    borderBottom: "1px solid #0f172a",
  },
  field: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  label: {
    color: "#64748b",
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },
  input: {
    background: "#0a1525",
    border: "1px solid #1e293b",
    borderRadius: 7,
    padding: "7px 10px",
    color: "#e2e8f0",
    fontSize: 12,
    fontFamily: "monospace",
    outline: "none",
    width: "100%",
    boxSizing: "border-box" as const,
  },
  hint: {
    color: "#334155",
    fontSize: 10,
    lineHeight: 1.4,
  },
  toggleRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 0",
    borderBottom: "1px solid #0d1526",
    gap: 12,
  },
  toggleLabel: {
    color: "#cbd5e1",
    fontSize: 12,
    fontWeight: 500,
  },
  toggleDesc: {
    color: "#475569",
    fontSize: 10,
    marginTop: 2,
    lineHeight: 1.4,
  },
  toggle: {
    width: 40,
    height: 22,
    borderRadius: 999,
    border: "none",
    cursor: "pointer",
    position: "relative" as const,
    flexShrink: 0,
    transition: "background 0.2s",
    padding: 0,
  },
  toggleThumb: {
    display: "block",
    width: 16,
    height: 16,
    borderRadius: "50%",
    background: "#fff",
    position: "absolute" as const,
    top: 3,
    transition: "transform 0.2s ease",
    boxShadow: "0 1px 4px rgba(0,0,0,0.4)",
  },
  versionRow: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: 12,
    fontSize: 10,
    paddingTop: 8,
    borderTop: "1px solid #0d1526",
  },
  center: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "40px 0",
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
