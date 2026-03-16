import { useState, useEffect, useCallback, useRef } from 'react'

export function usePolling(fetchFn, intervalMs = 30000, enabled = true) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      const result = await fetchFn()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    if (!enabled) return
    refresh()
    intervalRef.current = setInterval(refresh, intervalMs)
    return () => clearInterval(intervalRef.current)
  }, [refresh, intervalMs, enabled])

  return { data, loading, error, refresh }
}
