/**
 * EOD analysis, specialist analysis, backtest, and deploy endpoints.
 */

import { API_BASE, apiFetch } from './base'

// ── Backtest ──────────────────────────────────────────────────

export async function runBacktest(strategy, timeframe, capital, date) {
  const body = { strategy, timeframe, capital }
  if (date) body.date = date
  return apiFetch(`${API_BASE}/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// ── EOD Analysis ──────────────────────────────────────────────

export async function runEODAnalysis() {
  return apiFetch(`${API_BASE}/eod/analyse`, { method: 'POST' })
}

export async function applyEODRecommendations() {
  return apiFetch(`${API_BASE}/eod/apply`, { method: 'POST' })
}

export async function getStrategyConfig() {
  return apiFetch(`${API_BASE}/eod/config`)
}

// ── Algo Specialists ──────────────────────────────────────────

export async function getSpecialists() {
  return apiFetch(`${API_BASE}/specialists`)
}

export async function runSpecialistAnalysis(specialistId) {
  return apiFetch(`${API_BASE}/specialist/${specialistId}/analyse`, { method: 'POST' })
}

export async function deployRecommendation(deployKey) {
  return apiFetch(`${API_BASE}/specialist/deploy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deploy_key: deployKey }),
  })
}

// ── Capital Tracking ──────────────────────────────────────────

export async function setInitialCapital(amount, source = 'live') {
  return apiFetch(`${API_BASE}/capital/set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, source }),
  })
}

export async function addCapitalTransaction(amount, type, source = 'live', note = '') {
  return apiFetch(`${API_BASE}/capital/transaction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, type, source, note }),
  })
}

export async function getCapitalInfo(source = 'live') {
  return apiFetch(`${API_BASE}/capital/info?source=${source}`)
}

export async function deleteCapitalTransaction(index, source = 'live') {
  return apiFetch(`${API_BASE}/capital/transaction/${index}?source=${source}`, {
    method: 'DELETE',
  })
}
