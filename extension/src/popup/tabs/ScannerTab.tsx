// ============================================================
// ScannerTab — URL scanning with real-time result display
// ============================================================

import React, { useState, useEffect, useCallback } from "react"
import { useScan } from "~hooks/useScan"
import { ScanResultCard } from "~components/ScanResultCard"

interface ScannerTabProps {
  apiOnline: boolean
}

export function ScannerTab({ apiOnline }: ScannerTabProps) {
  const [url, setUrl] = useState("")
  const [currentTabUrl, setCurrentTabUrl] = useState("")
  const { loading, result, error, scanUrl, reset } = useScan()

  // Load the current tab URL automatically
  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabUrl = tabs[0]?.url || ""
      if (tabUrl.startsWith("http://") || tabUrl.startsWith("https://")) {
        setCurrentTabUrl(tabUrl)
        setUrl(tabUrl)
      }
    })

    // Load last scan result from storage
    chrome.storage.local.get("lastScanResult", ({ lastScanResult }) => {
      // Will be handled by the scanner on mount if auto-scan is enabled
    })
  }, [])

  const handleScan = useCallback(
    async (targetUrl?: string) => {
      const scanTarget = targetUrl || url
      if (!scanTarget) return
      reset()
      await scanUrl(scanTarget)
    },
    [url, scanUrl, reset]
  )

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleScan()
  }

  return (
    <div style={styles.container}>
      {/* URL Input */}
      <div style={styles.inputGroup}>
        <label style={styles.label}>URL to Scan</label>
        <div style={styles.inputRow}>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="https://example.com"
            style={styles.input}
            spellCheck={false}
            autoComplete="off"
          />
          <button
            onClick={() => handleScan()}
            disabled={loading || !url || !apiOnline}
            style={{
              ...styles.scanBtn,
              opacity: loading || !url || !apiOnline ? 0.5 : 1,
              cursor: loading || !url || !apiOnline ? "not-allowed" : "pointer",
            }}
          >
            {loading ? (
              <span style={styles.spinner} />
            ) : (
              "Scan"
            )}
          </button>
        </div>

        {/* Current Tab shortcut */}
        {currentTabUrl && currentTabUrl !== url && (
          <button
            style={styles.currentTabBtn}
            onClick={() => {
              setUrl(currentTabUrl)
              handleScan(currentTabUrl)
            }}
            disabled={!apiOnline}
          >
            🔍 Scan Current Tab
          </button>
        )}
      </div>

      {/* API offline warning */}
      {!apiOnline && (
        <div style={styles.offlineWarn}>
          <span>⚠️</span>
          <span>
            Backend is offline. Start the server with{" "}
            <code>python -m backend.app</code>
          </span>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div style={styles.loadingCard}>
          <div style={styles.loadingDots}>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  ...styles.dot,
                  animationDelay: `${i * 0.2}s`,
                }}
              />
            ))}
          </div>
          <span style={{ color: "#60a5fa", fontSize: 13 }}>
            Analysing URL with AI…
          </span>
        </div>
      )}

      {/* Result */}
      {!loading && result && <ScanResultCard result={result} />}

      {/* Error (non-result) */}
      {!loading && !result && error && (
        <div style={styles.errorText}>⚠️ {error}</div>
      )}
    </div>
  )
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  inputGroup: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  label: {
    color: "#64748b",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.5px",
    textTransform: "uppercase" as const,
  },
  inputRow: {
    display: "flex",
    gap: 8,
  },
  input: {
    flex: 1,
    background: "#0a1525",
    border: "1px solid #1e293b",
    borderRadius: 8,
    padding: "8px 12px",
    color: "#e2e8f0",
    fontSize: 12,
    fontFamily: "monospace",
    outline: "none",
    transition: "border-color 0.2s",
  },
  scanBtn: {
    background: "linear-gradient(135deg, #1d4ed8, #2563eb)",
    border: "none",
    borderRadius: 8,
    padding: "8px 16px",
    color: "#fff",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
    display: "flex",
    alignItems: "center",
    gap: 6,
    transition: "opacity 0.2s",
  },
  spinner: {
    display: "inline-block",
    width: 14,
    height: 14,
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    animation: "gs-spin 0.7s linear infinite",
  },
  currentTabBtn: {
    background: "transparent",
    border: "1px dashed #1e3a5f",
    borderRadius: 6,
    padding: "5px 10px",
    color: "#60a5fa",
    fontSize: 11,
    cursor: "pointer",
    textAlign: "left" as const,
    width: "100%",
  },
  offlineWarn: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 12px",
    borderRadius: 8,
    background: "rgba(251,191,36,0.06)",
    border: "1px solid rgba(251,191,36,0.2)",
    color: "#fde68a",
    fontSize: 11,
    lineHeight: 1.5,
  },
  loadingCard: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: 12,
    padding: "24px 0",
  },
  loadingDots: {
    display: "flex",
    gap: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "#3b82f6",
    animation: "gs-bounce 0.8s ease infinite",
  },
  errorText: {
    color: "#fca5a5",
    fontSize: 12,
    padding: "8px 12px",
    background: "rgba(239,68,68,0.05)",
    borderRadius: 6,
    border: "1px solid rgba(239,68,68,0.2)",
  },
}
