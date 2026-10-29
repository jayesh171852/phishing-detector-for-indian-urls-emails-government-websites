// ============================================================
// AI-GovShield — Background Service Worker (MV3)
// ============================================================
// Handles:
//   - Tab change monitoring → auto-scan new URLs
//   - Message routing between popup ↔ content scripts
//   - Scan orchestration via the FastAPI backend
//   - Persistent scan result cache in chrome.storage.local
//   - Chrome notifications for high-risk detections

import { GovShieldAPI } from "~api/client"
import {
  saveToHistory,
  getSettings,
  generateId,
  showNotification,
} from "~utils/helpers"
import type {
  ScanResult,
  URLPredictionResponse,
  EmailPredictionResponse,
  GovVerificationResponse,
  ExtensionMessage,
  ScanUrlMessage,
  ScanEmailMessage,
  EmailDetectedMessage,
} from "~types"

// ─── Tab Change Listener ──────────────────────────────────────

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only scan when the page has fully loaded
  if (changeInfo.status !== "complete" || !tab.url) return

  // Skip chrome:// and extension pages
  if (!tab.url.startsWith("http://") && !tab.url.startsWith("https://")) return

  const settings = await getSettings()
  if (!settings.autoScanOnLoad) return

  await runUrlScan(tab.url, tabId)
})

// ─── Message Router ───────────────────────────────────────────

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    sender: chrome.runtime.MessageSender,
    sendResponse: (response?: unknown) => void
  ) => {
    // Must return true for async sendResponse
    handleMessage(message, sender, sendResponse)
    return true
  }
)

async function handleMessage(
  message: ExtensionMessage,
  sender: chrome.runtime.MessageSender,
  sendResponse: (response?: unknown) => void
) {
  try {
    switch (message.type) {
      case "SCAN_URL": {
        const { url } = (message as ScanUrlMessage).payload
        const result = await runUrlScan(url)
        sendResponse({ success: true, result })
        break
      }

      case "SCAN_EMAIL": {
        const payload = (message as ScanEmailMessage).payload
        const result = await runEmailScan(
          payload.subject,
          payload.body,
          payload.sender
        )
        sendResponse({ success: true, result })
        break
      }

      case "EMAIL_DETECTED": {
        // Content script detected an email in Gmail/Outlook
        const payload = (message as EmailDetectedMessage).payload
        const result = await runEmailScan(
          payload.subject,
          payload.body,
          payload.sender
        )
        // Notify popup if it's open
        chrome.runtime.sendMessage({
          type: "SCAN_RESULT",
          payload: result,
        }).catch(() => {/* popup might be closed */})
        sendResponse({ success: true, result })
        break
      }

      case "GET_STATUS": {
        const { lastScanResult } = await chrome.storage.local.get(
          "lastScanResult"
        )
        const online = await checkApiHealth()
        sendResponse({ online, lastScanResult })
        break
      }

      case "GET_HISTORY": {
        const { history = [] } = await chrome.storage.local.get("history")
        sendResponse({ history })
        break
      }

      case "CLEAR_HISTORY": {
        await chrome.storage.local.set({ history: [], lastScanResult: undefined })
        sendResponse({ success: true })
        break
      }

      default:
        sendResponse({ success: false, error: "Unknown message type" })
    }
  } catch (err) {
    console.error("[GovShield BG] Message handling error:", err)
    sendResponse({ success: false, error: (err as Error).message })
  }
}

// ─── URL Scan Orchestrator ────────────────────────────────────

async function runUrlScan(
  url: string,
  tabId?: number
): Promise<ScanResult> {
  const settings = await getSettings()
  const id = generateId()

  let urlResult: URLPredictionResponse | undefined
  let govResult: GovVerificationResponse | undefined
  let scanError: Error | undefined

  try {
    urlResult = await GovShieldAPI.predictUrl({
      url,
      include_shap: settings.includeShap,
      include_gov_check: settings.enableGovCheck,
    })
    govResult = urlResult.gov_verification
  } catch (err) {
    console.warn("[GovShield BG] URL scan failed:", err)
    scanError = err instanceof Error ? err : new Error(String(err))
  }

  const result: ScanResult = {
    id,
    type: "url",
    url,
    timestamp: Date.now(),
    urlResult,
    govResult,
    error: urlResult ? undefined : scanError?.message,
  }

  await saveToHistory(result)

  // Notify for high/critical risk
  if (
    settings.showNotifications &&
    urlResult &&
    (urlResult.risk_level === "high" || urlResult.risk_level === "critical")
  ) {
    showNotification(
      "⚠️ Phishing Detected",
      `${urlResult.risk_level.toUpperCase()}: ${urlResult.message}`,
      urlResult.risk_level
    )
  }

  // Notify for government impersonation
  if (
    settings.showNotifications &&
    govResult?.is_impersonating
  ) {
    showNotification(
      "🚨 Fake Government Website",
      govResult.explanation.slice(0, 120),
      "critical"
    )
  }

  // Update extension badge
  updateBadge(tabId, urlResult?.risk_level)

  return result
}

// ─── Email Scan Orchestrator ──────────────────────────────────

async function runEmailScan(
  subject: string,
  body: string,
  sender?: string
): Promise<ScanResult> {
  const settings = await getSettings()
  const id = generateId()

  let emailResult: EmailPredictionResponse | undefined

  try {
    emailResult = await GovShieldAPI.predictEmail({ subject, body, sender })
  } catch (err) {
    console.warn("[GovShield BG] Email scan failed:", err)
  }

  const result: ScanResult = {
    id,
    type: "email",
    emailSubject: subject,
    timestamp: Date.now(),
    emailResult,
    error: emailResult ? undefined : "Email scan failed",
  }

  await saveToHistory(result)

  if (
    settings.showNotifications &&
    emailResult &&
    (emailResult.risk_level === "high" || emailResult.risk_level === "critical")
  ) {
    showNotification(
      "📧 Phishing Email Detected",
      emailResult.message.slice(0, 120),
      emailResult.risk_level
    )
  }

  return result
}

// ─── Badge Manager ────────────────────────────────────────────

function updateBadge(
  tabId: number | undefined,
  riskLevel?: string
) {
  const config: Record<string, { text: string; color: string }> = {
    safe:     { text: "✓",  color: "#34d399" },
    low:      { text: "!",  color: "#60a5fa" },
    medium:   { text: "!!",  color: "#fbbf24" },
    high:     { text: "!!!",  color: "#fb923c" },
    critical: { text: "🚨", color: "#f87171" },
  }

  const badgeConf = config[riskLevel ?? "low"] ?? config.low

  const target = tabId !== undefined ? { tabId } : {}

  chrome.action.setBadgeText({ text: badgeConf.text, ...target })
  chrome.action.setBadgeBackgroundColor({ color: badgeConf.color, ...target })
}

// ─── API Health Check ─────────────────────────────────────────

async function checkApiHealth(): Promise<boolean> {
  try {
    const health = await GovShieldAPI.health()
    return health.status === "healthy" || health.status === "degraded"
  } catch {
    return false
  }
}

// ─── Startup ──────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  console.log("[GovShield] Extension installed / updated.")
  // Set default badge
  chrome.action.setBadgeText({ text: "" })
})
