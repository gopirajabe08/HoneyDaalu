/**
 * Auto-trading, paper trading, swing trading start/stop/status,
 * trade history, daily P&L, and strategy stats endpoints.
 */

import { API_BASE, apiFetch } from './base'

// ── Equity Market Regime ──────────────────────────────────────

export async function getEquityRegime() {
  return apiFetch(`${API_BASE}/equity/regime`)
}

export async function startAutoTradingRegime(capital) {
  return apiFetch(`${API_BASE}/auto/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

export async function startPaperTradingRegime(capital) {
  return apiFetch(`${API_BASE}/paper/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

// ── Auto-Trading (Intraday Live) ──────────────────────────────

export async function startAutoTrading(strategies, capital) {
  return apiFetch(`${API_BASE}/auto/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital }),
  })
}

export async function stopAutoTrading() {
  return apiFetch(`${API_BASE}/auto/stop`, { method: 'POST' })
}

export async function getAutoStatus() {
  return apiFetch(`${API_BASE}/auto/status`)
}

// ── Paper Trading (Intraday) ──────────────────────────────────

export async function startPaperTrading(strategies, capital) {
  return apiFetch(`${API_BASE}/paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital }),
  })
}

export async function stopPaperTrading() {
  return apiFetch(`${API_BASE}/paper/stop`, { method: 'POST' })
}

export async function getPaperStatus() {
  return apiFetch(`${API_BASE}/paper/status`)
}

// ── Swing Trading (Live) ──────────────────────────────────────

export async function startSwingTrading(strategies, capital, scanIntervalMinutes = 240) {
  return apiFetch(`${API_BASE}/swing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital, scan_interval_minutes: scanIntervalMinutes }),
  })
}

export async function stopSwingTrading() {
  return apiFetch(`${API_BASE}/swing/stop`, { method: 'POST' })
}

export async function getSwingStatus() {
  return apiFetch(`${API_BASE}/swing/status`)
}

// ── Swing Paper Trading ───────────────────────────────────────

export async function startSwingPaperTrading(strategies, capital, scanIntervalMinutes = 240) {
  return apiFetch(`${API_BASE}/swing-paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital, scan_interval_minutes: scanIntervalMinutes }),
  })
}

export async function startSwingTradingRegime(capital) {
  return apiFetch(`${API_BASE}/swing/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

export async function startSwingPaperTradingRegime(capital) {
  return apiFetch(`${API_BASE}/swing-paper/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

export async function stopSwingPaperTrading() {
  return apiFetch(`${API_BASE}/swing-paper/stop`, { method: 'POST' })
}

export async function getSwingPaperStatus() {
  return apiFetch(`${API_BASE}/swing-paper/status`)
}

// ── Strategy Stats & Trade History ────────────────────────────

export async function getStrategyStats(source = null) {
  const url = source ? `${API_BASE}/strategy/stats?source=${source}` : `${API_BASE}/strategy/stats`
  return apiFetch(url)
}

export async function getTradeHistory(days = 30, source = null) {
  const params = new URLSearchParams({ days })
  if (source) params.append('source', source)
  return apiFetch(`${API_BASE}/trades/history?${params}`)
}

export async function getDailyPnl(days = 30, source = null) {
  const params = new URLSearchParams({ days })
  if (source) params.append('source', source)
  return apiFetch(`${API_BASE}/trades/daily-pnl?${params}`)
}
