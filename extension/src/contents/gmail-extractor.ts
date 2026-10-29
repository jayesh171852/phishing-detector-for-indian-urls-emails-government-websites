// ============================================================
// AI-GovShield — Gmail Content Script
// ============================================================
// Injected into https://mail.google.com/* pages.
// Watches for email opens and extracts subject + body, then
// sends them to the background worker for phishing analysis.

import type { EmailDetectedMessage } from "~types"

// Plasmo content script config — matches Gmail
export const config = {
  matches: ["https://mail.google.com/*"],
  run_at: "document_idle",
}

// ─── State ────────────────────────────────────────────────────

let lastProcessedSubject = ""
let observer: MutationObserver | null = null

// ─── Entry Point ──────────────────────────────────────────────

init()

function init() {
  // Gmail loads asynchronously — wait for the DOM to settle
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watchGmail)
  } else {
    watchGmail()
  }
}

function watchGmail() {
  // MutationObserver watches for Gmail's dynamic email panel
  observer = new MutationObserver(debounce(onDomChange, 800))
  observer.observe(document.body, { childList: true, subtree: true })
}

// ─── DOM Change Handler ───────────────────────────────────────

function onDomChange() {
  const emailData = extractEmailFromGmail()
  if (!emailData) return
  if (emailData.subject === lastProcessedSubject) return // already scanned

  lastProcessedSubject = emailData.subject
  sendToBackground(emailData)
  injectScanIndicator(emailData.subject)
}

// ─── Gmail Email Extractor ────────────────────────────────────

interface ExtractedEmail {
  subject: string
  body: string
  sender: string
}

function extractEmailFromGmail(): ExtractedEmail | null {
  // Gmail DOM selectors (updated for current Gmail layout)
  const subjectEl =
    document.querySelector<HTMLElement>('h2[data-thread-perm-id]') ||
    document.querySelector<HTMLElement>('.hP') ||          // conversation header
    document.querySelector<HTMLElement>('[data-legacy-thread-id] h2')

  const bodyEls = document.querySelectorAll<HTMLElement>('.a3s.aiL, .a3s.aXjCH')
  const senderEl =
    document.querySelector<HTMLElement>('.gD[email]') ||
    document.querySelector<HTMLElement>('[data-hovercard-id]')

  if (!subjectEl) return null

  const subject = subjectEl.textContent?.trim() || ""
  if (!subject || subject.length < 2) return null

  // Collect all visible body paragraphs
  const bodyParts: string[] = []
  bodyEls.forEach((el) => {
    const text = el.innerText?.trim()
    if (text) bodyParts.push(text)
  })

  const body = bodyParts.join("\n\n")
  const sender =
    senderEl?.getAttribute("email") ||
    senderEl?.textContent?.trim() ||
    ""

  if (!body || body.length < 10) return null

  return { subject, body, sender }
}

// ─── Send to Background ───────────────────────────────────────

function sendToBackground(email: ExtractedEmail) {
  const message: EmailDetectedMessage = {
    type: "EMAIL_DETECTED",
    payload: {
      subject: email.subject,
      body: email.body.slice(0, 5000), // cap length
      sender: email.sender,
    },
  }

  chrome.runtime.sendMessage(message, (response) => {
    if (chrome.runtime.lastError) return
    if (response?.result) {
      injectResultBanner(response.result)
    }
  })
}

// ─── Inject Scan Indicator ────────────────────────────────────

function injectScanIndicator(subject: string) {
  // Remove any existing indicator
  document.getElementById("govshield-scan-indicator")?.remove()

  const indicator = document.createElement("div")
  indicator.id = "govshield-scan-indicator"
  indicator.style.cssText = `
    position: fixed;
    bottom: 16px;
    right: 16px;
    background: #0f1729;
    border: 1px solid #1e40af;
    border-radius: 8px;
    padding: 8px 14px;
    color: #93c5fd;
    font-family: -apple-system, sans-serif;
    font-size: 12px;
    font-weight: 500;
    z-index: 99999;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    animation: govshield-fadeIn 0.3s ease;
  `
  indicator.innerHTML = `
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
      background:#3b82f6;animation:govshield-pulse 1s infinite;"></span>
    AI-GovShield: Scanning email…
  `
  injectStyles()
  document.body.appendChild(indicator)

  // Auto-remove after 3s
  setTimeout(() => indicator.remove(), 3000)
}

// ─── Inject Result Banner ─────────────────────────────────────

function injectResultBanner(result: any) {
  document.getElementById("govshield-result-banner")?.remove()

  const emailResult = result.emailResult
  if (!emailResult) return

  const isPhishing = emailResult.is_phishing
  const confidence = Math.round(emailResult.confidence * 100)

  const banner = document.createElement("div")
  banner.id = "govshield-result-banner"
  banner.style.cssText = `
    position: fixed;
    bottom: 16px;
    right: 16px;
    background: ${isPhishing ? "#1a0a0a" : "#0a1a0f"};
    border: 1.5px solid ${isPhishing ? "#dc2626" : "#16a34a"};
    border-radius: 10px;
    padding: 12px 16px;
    color: ${isPhishing ? "#fca5a5" : "#86efac"};
    font-family: -apple-system, sans-serif;
    font-size: 13px;
    font-weight: 600;
    z-index: 99999;
    max-width: 300px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    cursor: pointer;
    animation: govshield-slideIn 0.3s ease;
  `
  banner.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
      <span style="font-size:16px">${isPhishing ? "🚨" : "✅"}</span>
      <span>${isPhishing ? "PHISHING EMAIL DETECTED" : "Email Appears Safe"}</span>
      <span style="margin-left:auto;font-size:11px;opacity:0.7" id="govshield-close-btn">✕</span>
    </div>
    <div style="font-size:11px;font-weight:400;opacity:0.85">
      Confidence: ${confidence}% · Risk: ${emailResult.risk_level?.toUpperCase()}
    </div>
  `

  document.body.appendChild(banner)

  // Dismiss on click
  banner.querySelector("#govshield-close-btn")?.addEventListener("click", (e) => {
    e.stopPropagation()
    banner.remove()
  })
  setTimeout(() => banner?.remove(), 8000)
}

// ─── Inject Keyframe Styles ───────────────────────────────────

function injectStyles() {
  if (document.getElementById("govshield-styles")) return
  const style = document.createElement("style")
  style.id = "govshield-styles"
  style.textContent = `
    @keyframes govshield-pulse {
      0%, 100% { opacity: 1; } 50% { opacity: 0.3; }
    }
    @keyframes govshield-fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes govshield-slideIn {
      from { opacity: 0; transform: translateX(20px); }
      to { opacity: 1; transform: translateX(0); }
    }
  `
  document.head.appendChild(style)
}

// ─── Debounce ─────────────────────────────────────────────────

function debounce<T extends (...args: any[]) => void>(fn: T, ms: number): T {
  let timer: ReturnType<typeof setTimeout>
  return ((...args: any[]) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), ms)
  }) as T
}
