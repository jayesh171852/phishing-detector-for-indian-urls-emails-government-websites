// ============================================================
// AI-GovShield — Main Popup
// ============================================================
// Entry point rendered when user clicks the extension icon.
// Houses the tabbed layout: Scanner | Email | History | Settings

import React, { useState, useEffect } from "react"
import "../styles/globals.css"

import { ScannerTab } from "./tabs/ScannerTab"
import { EmailTab } from "./tabs/EmailTab"
import { HistoryTab } from "./tabs/HistoryTab"
import { SettingsTab } from "./tabs/SettingsTab"
import { ApiStatusBar } from "~components/ApiStatusBar"
import { useApiStatus } from "~hooks/useApiStatus"

type Tab = "scanner" | "email" | "history" | "settings"

const NAV_ITEMS: { id: Tab; icon: string; label: string }[] = [
  { id: "scanner", icon: "🛡️", label: "Scanner" },
  { id: "email",   icon: "📧", label: "Email" },
  { id: "history", icon: "📋", label: "History" },
  { id: "settings",icon: "⚙️", label: "Settings" },
]

export default function Popup() {
  const [activeTab, setActiveTab] = useState<Tab>("scanner")
  const { online, health, checking } = useApiStatus()

  return (
    <div style={styles.root}>
      {/* ── Top Header ── */}
      <header style={styles.header}>
        <div style={styles.logoRow}>
          <img
            src="/assets/icon128.png"
            alt="GovShield"
            width={28}
            height={28}
            style={{ borderRadius: 6 }}
            onError={(e) => {
              // fallback if icon not yet generated
              ;(e.target as HTMLImageElement).style.display = "none"
            }}
          />
          <div>
            <div style={styles.logoText}>AI-GovShield</div>
            <div style={styles.logoSub}>Phishing Detection System</div>
          </div>
        </div>
        <ApiStatusBar
          online={online}
          checking={checking}
          modelStatus={health?.models}
        />
      </header>

      {/* ── Tab Content ── */}
      <main style={styles.content}>
        {activeTab === "scanner"  && <ScannerTab apiOnline={online} />}
        {activeTab === "email"    && <EmailTab apiOnline={online} />}
        {activeTab === "history"  && <HistoryTab />}
        {activeTab === "settings" && <SettingsTab />}
      </main>

      {/* ── Bottom Nav ── */}
      <nav style={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            style={{
              ...styles.navBtn,
              ...(activeTab === item.id ? styles.navBtnActive : {}),
            }}
            onClick={() => setActiveTab(item.id)}
            aria-label={item.label}
            title={item.label}
          >
            <span style={styles.navIcon}>{item.icon}</span>
            <span
              style={{
                ...styles.navLabel,
                color: activeTab === item.id ? "#60a5fa" : "#475569",
              }}
            >
              {item.label}
            </span>
          </button>
        ))}
      </nav>
    </div>
  )
}

// ─── Styles ───────────────────────────────────────────────────

const styles = {
  root: {
    width: 400,
    minHeight: 560,
    maxHeight: 600,
    background: "#060d1a",
    display: "flex",
    flexDirection: "column" as const,
    fontFamily: "'Inter', -apple-system, 'Segoe UI', sans-serif",
    color: "#e2e8f0",
    overflow: "hidden",
  },
  header: {
    background: "linear-gradient(135deg, #0a1628 0%, #0f1f3d 100%)",
    borderBottom: "1px solid #1e293b",
    padding: "10px 14px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  logoRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  logoText: {
    color: "#60a5fa",
    fontWeight: 800,
    fontSize: 14,
    letterSpacing: "0.3px",
  },
  logoSub: {
    color: "#334155",
    fontSize: 9,
    letterSpacing: "0.5px",
    textTransform: "uppercase" as const,
  },
  content: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "12px 14px",
    scrollbarWidth: "thin" as const,
    scrollbarColor: "#1e293b #060d1a",
  },
  nav: {
    background: "#080f1c",
    borderTop: "1px solid #1e293b",
    display: "flex",
    justifyContent: "space-around",
    padding: "6px 0",
  },
  navBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: 2,
    padding: "4px 12px",
    borderRadius: 8,
    transition: "background 0.15s",
  },
  navBtnActive: {
    background: "rgba(96,165,250,0.08)",
  },
  navIcon: {
    fontSize: 17,
  },
  navLabel: {
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: "0.3px",
    textTransform: "uppercase" as const,
    transition: "color 0.15s",
  },
}
