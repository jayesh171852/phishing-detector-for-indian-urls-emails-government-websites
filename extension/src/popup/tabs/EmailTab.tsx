// ============================================================
// EmailTab — manual email phishing analysis
// ============================================================

import React, { useState } from "react"
import { useScan } from "~hooks/useScan"
import { EmailResultCard } from "~components/EmailResultCard"

interface EmailTabProps {
  apiOnline: boolean
}

export function EmailTab({ apiOnline }: EmailTabProps) {
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [sender, setSender] = useState("")
  const { loading, result, error, scanEmail, reset } = useScan()

  const handleScan = async () => {
    if (!body.trim()) return
    reset()
    await scanEmail(subject, body, sender || undefined)
  }

  const handleClear = () => {
    setSubject("")
    setBody("")
    setSender("")
    reset()
  }

  return (
    <div style={styles.container}>
      <div style={styles.hint}>
        Paste a suspicious email below to check for phishing.
        Gmail/Outlook emails are scanned automatically.
      </div>

      {/* Sender (optional) */}
      <div style={styles.field}>
        <label style={styles.label}>From (optional)</label>
        <input
          type="text"
          value={sender}
          onChange={(e) => setSender(e.target.value)}
          placeholder="sender@example.com"
          style={styles.input}
          autoComplete="off"
        />
      </div>

      {/* Subject */}
      <div style={styles.field}>
        <label style={styles.label}>Subject *</label>
        <input
          type="text"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Email subject line…"
          style={styles.input}
        />
      </div>

      {/* Body */}
      <div style={styles.field}>
        <label style={styles.label}>Email Body *</label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Paste the email content here…"
          style={styles.textarea}
          rows={5}
        />
        <div style={styles.charCount}>{body.length} / 5000 chars</div>
      </div>

      {/* Actions */}
      <div style={styles.btnRow}>
        <button
          onClick={handleScan}
          disabled={loading || !body.trim() || !apiOnline}
          style={{
            ...styles.scanBtn,
            opacity: loading || !body.trim() || !apiOnline ? 0.5 : 1,
            cursor: loading || !body.trim() || !apiOnline ? "not-allowed" : "pointer",
          }}
        >
          {loading ? (
            <>
              <span style={styles.spinner} />
              Analysing…
            </>
          ) : (
            "🔍 Analyse Email"
          )}
        </button>
        <button onClick={handleClear} style={styles.clearBtn}>
          Clear
        </button>
      </div>

      {!apiOnline && (
        <div style={styles.offlineWarn}>
          ⚠️ Backend offline. Start the server first.
        </div>
      )}

      {loading && (
        <div style={styles.loadingMsg}>
          <span style={styles.spinnerLg} />
          Analysing with ModernBERT…
        </div>
      )}

      {!loading && result && result.emailResult && (
        <EmailResultCard result={result} />
      )}

      {!loading && error && (
        <div style={styles.errorText}>⚠️ {error}</div>
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
  hint: {
    color: "#475569",
    fontSize: 11,
    lineHeight: 1.5,
    padding: "6px 10px",
    borderRadius: 6,
    background: "rgba(30,41,59,0.5)",
    border: "1px solid #1e293b",
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
    letterSpacing: "0.5px",
    textTransform: "uppercase" as const,
  },
  input: {
    background: "#0a1525",
    border: "1px solid #1e293b",
    borderRadius: 7,
    padding: "7px 10px",
    color: "#e2e8f0",
    fontSize: 12,
    outline: "none",
    width: "100%",
    boxSizing: "border-box" as const,
  },
  textarea: {
    background: "#0a1525",
    border: "1px solid #1e293b",
    borderRadius: 7,
    padding: "7px 10px",
    color: "#e2e8f0",
    fontSize: 12,
    outline: "none",
    width: "100%",
    boxSizing: "border-box" as const,
    resize: "vertical" as const,
    fontFamily: "inherit",
    lineHeight: 1.5,
  },
  charCount: {
    color: "#334155",
    fontSize: 10,
    textAlign: "right" as const,
    marginTop: 2,
  },
  btnRow: {
    display: "flex",
    gap: 8,
  },
  scanBtn: {
    flex: 1,
    background: "linear-gradient(135deg, #1d4ed8, #2563eb)",
    border: "none",
    borderRadius: 8,
    padding: "9px",
    color: "#fff",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  clearBtn: {
    background: "transparent",
    border: "1px solid #1e293b",
    borderRadius: 8,
    padding: "9px 14px",
    color: "#64748b",
    fontSize: 12,
    cursor: "pointer",
  },
  spinner: {
    display: "inline-block",
    width: 13,
    height: 13,
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    animation: "gs-spin 0.7s linear infinite",
  },
  spinnerLg: {
    display: "inline-block",
    width: 18,
    height: 18,
    border: "2px solid rgba(96,165,250,0.3)",
    borderTopColor: "#60a5fa",
    borderRadius: "50%",
    animation: "gs-spin 0.7s linear infinite",
  },
  loadingMsg: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    color: "#60a5fa",
    fontSize: 13,
    padding: "16px 0",
  },
  offlineWarn: {
    color: "#fde68a",
    fontSize: 11,
    padding: "6px 10px",
    borderRadius: 6,
    background: "rgba(251,191,36,0.06)",
    border: "1px solid rgba(251,191,36,0.2)",
  },
  errorText: {
    color: "#fca5a5",
    fontSize: 12,
    padding: "8px 10px",
    background: "rgba(239,68,68,0.05)",
    borderRadius: 6,
    border: "1px solid rgba(239,68,68,0.2)",
  },
}
