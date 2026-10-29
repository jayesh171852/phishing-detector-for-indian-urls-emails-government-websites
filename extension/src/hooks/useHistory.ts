// ============================================================
// useHistory — loads and manages scan history from storage
// ============================================================

import { useState, useEffect, useCallback } from "react"
import { getHistory, clearHistory } from "~utils/helpers"
import type { ScanResult } from "~types"

export function useHistory() {
  const [history, setHistory] = useState<ScanResult[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    const items = await getHistory()
    setHistory(items)
    setLoading(false)
  }, [])

  const clear = useCallback(async () => {
    await clearHistory()
    setHistory([])
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { history, loading, reload: load, clear }
}
