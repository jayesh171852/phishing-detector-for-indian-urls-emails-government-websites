// ============================================================
// AI-GovShield — Outlook Content Script
// ============================================================
// Injected into https://outlook.live.com/* and
// https://outlook.office.com/* pages.
// Watches the reading pane for email content and extracts
// subject + body for phishing analysis.

import type { EmailDetectedMessage } from "~types"

export const config = {
  matches: [
    "https://outlook.live.com/*",
    "https://outlook.office.com/*",
    "https://outlook.office365.com/*",
  ],
  run_at: "document_idle",
}

let lastSubject = ""
let observer: MutationObserver | null = null

init()

function init() {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watchOutlook)
  } else {
    watchOutlook()
  }
}

function watchOutlook() {
  observer = new MutationObserver(debounce(onDomChange, 900))
  observer.observe(document.body, { childList: true, subtree: true })
}

function onDomChange() {
  const email = extractEmailFromOutlook()
  if (!email || email.subject === lastSubject) return
  lastSubject = email.subject
  sendToBackground(email)
}

// ─── Outlook Email Extractor ──────────────────────────────────

interface ExtractedEmail {
  subject: string
  body: string
  sender: string
}

function extractEmailFromOutlook(): ExtractedEmail | null {
  // Outlook web selectors (Outlook New + Classic)
  const subjectEl =
    document.querySelector<HTMLElement>('[data-testid="ConversationHeader-Subject"]') ||
    document.querySelector<HTMLElement>('.allowTextSelection.GeMJHC') ||
    document.querySelector<HTMLElement>('[aria-label="Message subject"]') ||
    document.querySelector<HTMLElement>('.Subject span')

  const bodyEl =
    document.querySelector<HTMLElement>('[data-testid="MessageBody"]') ||
    document.querySelector<HTMLElement>('.ReadingPaneContent') ||
    document.querySelector<HTMLElement>('[aria-label="Message body"]') ||
    document.querySelector<HTMLElement>('.allowTextSelection')

  const senderEl =
    document.querySelector<HTMLElement>('[data-testid="SenderInfo-SenderName"]') ||
    document.querySelector<HTMLElement>('.allowTextSelection.hJnHEe') ||
    document.querySelector<HTMLElement>('[aria-label^="From:"]')

  if (!subjectEl || !bodyEl) return null

  const subject = subjectEl.textContent?.trim() || ""
  const body = bodyEl.innerText?.trim() || ""
  const sender = senderEl?.textContent?.trim() || ""

  if (!subject || !body || body.length < 10) return null

  return { subject, body, sender }
}

function sendToBackground(email: ExtractedEmail) {
  const message: EmailDetectedMessage = {
    type: "EMAIL_DETECTED",
    payload: {
      subject: email.subject,
      body: email.body.slice(0, 5000),
      sender: email.sender,
    },
  }
  chrome.runtime.sendMessage(message, (response) => {
    if (chrome.runtime.lastError) return
    if (response?.result) {
      showResultToast(response.result)
    }
  })
}

function showResultToast(result: any) {
  document.getElementById("govshield-outlook-toast")?.remove()

  const emailResult = result.emailResult
  if (!emailResult) return

  const isPhishing = emailResult.is_phishing
  const confidence = Math.round(emailResult.confidence * 100)

  const toast = document.createElement("div")
  toast.id = "govshield-outlook-toast"
  toast.style.cssText = `
    position: fixed;
    top: 70px;
    right: 16px;
    background: ${isPhishing ? "#1a0505" : "#051a0a"};
    border: 1.5px solid ${isPhishing ? "#ef4444" : "#22c55e"};
    border-radius: 10px;
    padding: 12px 16px;
    color: ${isPhishing ? "#fca5a5" : "#86efac"};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    font-weight: 600;
    z-index: 99999;
    max-width: 280px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5);
  `
  toast.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
      <span>${isPhishing ? "🚨" : "✅"}</span>
      <span>${isPhishing ? "Phishing Email!" : "Email Appears Safe"}</span>
    </div>
    <div style="font-size:11px;font-weight:400;opacity:0.8">
      ${confidence}% confidence · ${emailResult.risk_level?.toUpperCase()} risk
    </div>
  `

  document.body.appendChild(toast)
  setTimeout(() => toast?.remove(), 6000)
}

function debounce<T extends (...args: any[]) => void>(fn: T, ms: number): T {
  let timer: ReturnType<typeof setTimeout>
  return ((...args: any[]) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), ms)
  }) as T
}
