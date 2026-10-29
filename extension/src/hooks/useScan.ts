// ============================================================
// useScan — drives URL / email scan from the popup
// ============================================================

import { useState, useCallback } from "react"
import { GovShieldAPI } from "~api/client"
import { generateId, saveToHistory, getSettings } from "~utils/helpers"
import type {
  ScanResult,
  URLPredictionResponse,
  EmailPredictionResponse,
  GovVerificationResponse,
} from "~types"

export function useScan() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const scanUrl = useCallback(async (url: string): Promise<ScanResult> => {
    setLoading(true)
    setError(null)

    try {
      const settings = await getSettings()
      const urlResult: URLPredictionResponse = await GovShieldAPI.predictUrl({
        url,
        include_shap: settings.includeShap,
        include_gov_check: settings.enableGovCheck,
      })

      const govResult: GovVerificationResponse | undefined =
        urlResult.gov_verification

      const scan: ScanResult = {
        id: generateId(),
        type: "url",
        url,
        timestamp: Date.now(),
        urlResult,
        govResult,
      }

      await saveToHistory(scan)
      setResult(scan)
      return scan
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      const scan: ScanResult = {
        id: generateId(),
        type: "url",
        url,
        timestamp: Date.now(),
        error: msg,
      }
      setResult(scan)
      return scan
    } finally {
      setLoading(false)
    }
  }, [])

  const scanEmail = useCallback(
    async (subject: string, body: string, sender?: string): Promise<ScanResult> => {
      setLoading(true)
      setError(null)

      try {
        const emailResult: EmailPredictionResponse =
          await GovShieldAPI.predictEmail({ subject, body, sender })

        const scan: ScanResult = {
          id: generateId(),
          type: "email",
          emailSubject: subject,
          timestamp: Date.now(),
          emailResult,
        }

        await saveToHistory(scan)
        setResult(scan)
        return scan
      } catch (err) {
        const msg = (err as Error).message
        setError(msg)
        const scan: ScanResult = {
          id: generateId(),
          type: "email",
          emailSubject: subject,
          timestamp: Date.now(),
          error: msg,
        }
        setResult(scan)
        return scan
      } finally {
        setLoading(false)
      }
    },
    []
  )

  const reset = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  return { loading, result, error, scanUrl, scanEmail, reset }
}
