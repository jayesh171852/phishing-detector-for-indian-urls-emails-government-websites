// ============================================================
// useApiStatus — polls backend health every 30s
// ============================================================

import { useState, useEffect, useCallback } from "react"
import { GovShieldAPI } from "~api/client"
import type { HealthResponse } from "~types"

export function useApiStatus() {
  const [online, setOnline] = useState<boolean>(false)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [checking, setChecking] = useState(true)

  const check = useCallback(async () => {
    setChecking(true)
    try {
      const data = await GovShieldAPI.health()
      setHealth(data)
      setOnline(true)
    } catch {
      setOnline(false)
      setHealth(null)
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => {
    check()
    const interval = setInterval(check, 30_000)
    return () => clearInterval(interval)
  }, [check])

  return { online, health, checking, refetch: check }
}
