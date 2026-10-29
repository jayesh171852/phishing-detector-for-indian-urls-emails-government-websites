// ============================================================
// useSettings — loads and persists extension settings
// ============================================================

import { useState, useEffect, useCallback } from "react"
import { getSettings, saveSettings } from "~utils/helpers"
import type { ExtensionSettings } from "~types"

export function useSettings() {
  const [settings, setSettings] = useState<ExtensionSettings | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSettings().then((s) => {
      setSettings(s)
      setLoading(false)
    })
  }, [])

  const update = useCallback(
    async (partial: Partial<ExtensionSettings>) => {
      const updated = await saveSettings(partial)
      setSettings(updated)
      // Broadcast to content scripts
      chrome.runtime.sendMessage({ type: "SETTINGS_UPDATED", payload: updated })
      return updated
    },
    []
  )

  return { settings, loading, update }
}
