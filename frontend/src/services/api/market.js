/**
 * Market status, strategies, and scan endpoints.
 */

import { API_BASE, apiFetch } from './base'

export async function getMarketStatus() {
  return apiFetch(`${API_BASE}/market/status`)
}

export async function fetchStrategies() {
  return apiFetch(`${API_BASE}/strategies`)
}

export async function fetchScanResults(strategyId, timeframe, capital) {
  const params = new URLSearchParams({
    timeframe,
    capital: capital.toString(),
  })
  return apiFetch(`${API_BASE}/scan/${strategyId}?${params}`)
}

export async function fetchTimeframes(strategyId) {
  return apiFetch(`${API_BASE}/timeframes/${strategyId}`)
}
