// ============================================================
// AI-GovShield — Universal Page Scanner Content Script
// ============================================================
// Injected into all http/https pages.
// Responsibilities:
//   1. Report current URL + page metadata to the background worker
//   2. Inject a warning overlay when a phishing/fake-gov result arrives
//   3. Respond to popup "manual scan" trigger

import type { ScanResult } from "~types"

export const config = {
  matches: ["https://*/*", "http://*/*"],
  exclude_matches: [
    "https://mail.google.com/*",
    "https://outlook.live.com/*",
    "https://outlook.office.com/*",
    "https://outlook.office365.com/*",
  ],
  run_at: "document_idle",
}

// ─── Announce page to background ─────────────────────────────

function announcePage() {
  chrome.runtime.sendMessage({
    type: "SCAN_URL",
    payload: { url: window.location.href },
  }, (response) => {
    if (chrome.runtime.lastError) return
    if (response?.result) {
      handleScanResult(response.result as ScanResult)
    }
  })
}

// ─── Handle incoming scan result ─────────────────────────────

function handleScanResult(result: ScanResult) {
  const risk = result.urlResult?.risk_level
  const isPhishing = result.urlResult?.is_phishing
  const isGovFake = result.govResult?.is_impersonating

  // Only show overlay for high / critical risk OR gov impersonation
  if (!isPhishing && !isGovFake) return
  if (risk !== "high" && risk !== "critical" && !isGovFake) return

  injectWarningOverlay(result)
}

// ─── Phishing Warning Overlay ─────────────────────────────────

function injectWarningOverlay(result: ScanResult) {
  if (document.getElementById("govshield-warning-overlay")) return

  injectKeyframes()

  const overlay = document.createElement("div")
  overlay.id = "govshield-warning-overlay"

  const isGovFake = result.govResult?.is_impersonating
  const confidence = result.urlResult
    ? `${Math.round(result.urlResult.confidence * 100)}%`
    : ""

  overlay.style.cssText = `
    position: fixed;
    top: 0; left: 0; right: 0;
    background: linear-gradient(135deg, #1a0505 0%, #0f1729 100%);
    border-bottom: 2px solid #dc2626;
    padding: 14px 20px;
    z-index: 2147483647;
    font-family: -apple-system, 'Segoe UI', sans-serif;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 4px 30px rgba(220,38,38,0.4);
    animation: govshield-slideDown 0.4s ease;
  `

  overlay.innerHTML = `
    <div style="flex-shrink:0;font-size:28px">${isGovFake ? "🏛️" : "🚨"}</div>
    <div style="flex:1">
      <div style="color:#fca5a5;font-weight:700;font-size:14px;letter-spacing:0.5px">
        ${isGovFake
          ? "⚠ FAKE GOVERNMENT WEBSITE DETECTED"
          : "⚠ PHISHING WEBSITE DETECTED"
        }
      </div>
      <div style="color:#fecaca;font-size:12px;margin-top:3px;opacity:0.85">
        ${isGovFake
          ? `This site impersonates: <strong style="color:#fb7185">${result.govResult?.matched_domain ?? "a government portal"}</strong>. Do not enter credentials.`
          : `AI-GovShield flagged this URL as malicious with ${confidence} confidence. Proceed with extreme caution.`
        }
      </div>
    </div>
    <button id="govshield-dismiss-btn" style="
      background: transparent;
      border: 1px solid #dc2626;
      color: #fca5a5;
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 12px;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s;
    ">Dismiss</button>
  `

  // Inject keyframes once
  document.documentElement.insertBefore(overlay, document.documentElement.firstChild)

  document.getElementById("govshield-dismiss-btn")?.addEventListener("click", () => {
    overlay.style.animation = "govshield-slideUp 0.3s ease forwards"
    setTimeout(() => overlay.remove(), 300)
  })
}

function injectKeyframes() {
  if (document.getElementById("govshield-keyframes")) return
  const style = document.createElement("style")
  style.id = "govshield-keyframes"
  style.textContent = `
    @keyframes govshield-slideDown {
      from { transform: translateY(-100%); opacity: 0; }
      to   { transform: translateY(0);    opacity: 1; }
    }
    @keyframes govshield-slideUp {
      from { transform: translateY(0);    opacity: 1; }
      to   { transform: translateY(-100%); opacity: 0; }
    }
  `
  document.head.appendChild(style)
}

// ─── Listen for messages from popup ──────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "PING") {
    sendResponse({ url: window.location.href, title: document.title })
  }
  return true
})

// ─── Boot ─────────────────────────────────────────────────────

// Small delay to let SPA frameworks settle
setTimeout(announcePage, 500)
