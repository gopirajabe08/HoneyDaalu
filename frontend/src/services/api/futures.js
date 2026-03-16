/**
 * Futures trading endpoints — strategies, OI analysis,
 * and all four trader controls (auto/paper x intraday/swing).
 */

import { API_BASE, apiFetch } from './base'

// ── Futures Strategies & Data ─────────────────────────────────

export async function getFuturesStrategies() {
  return apiFetch(`${API_BASE}/futures/strategies`)
}

export async function getFuturesOI(symbol) {
  return apiFetch(`${API_BASE}/futures/oi/${symbol}`)
}

export async function getFuturesRegime() {
  return apiFetch(`${API_BASE}/futures/regime`)
}

// ── Auto Strategy Selection (regime-based) ────────────────────

export async function startFuturesAutoRegime(capital) {
  return apiFetch(`${API_BASE}/futures/auto/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

export async function startFuturesPaperRegime(capital) {
  return apiFetch(`${API_BASE}/futures/paper/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

export async function startFuturesSwingRegime(capital) {
  return apiFetch(`${API_BASE}/futures/swing/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

export async function startFuturesSwingPaperRegime(capital) {
  return apiFetch(`${API_BASE}/futures/swing-paper/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

// ── Futures Auto-Trading (Intraday Live) ──────────────────────

export async function startFuturesAutoTrading(strategies, capital) {
  return apiFetch(`${API_BASE}/futures/auto/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital }),
  })
}

export async function stopFuturesAutoTrading() {
  return apiFetch(`${API_BASE}/futures/auto/stop`, { method: 'POST' })
}

export async function getFuturesAutoStatus() {
  return apiFetch(`${API_BASE}/futures/auto/status`)
}

// ── Futures Paper Trading (Intraday Virtual) ──────────────────

export async function startFuturesPaperTrading(strategies, capital) {
  return apiFetch(`${API_BASE}/futures/paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital }),
  })
}

export async function stopFuturesPaperTrading() {
  return apiFetch(`${API_BASE}/futures/paper/stop`, { method: 'POST' })
}

export async function getFuturesPaperStatus() {
  return apiFetch(`${API_BASE}/futures/paper/status`)
}

// ── Futures Swing Trading (Live) ──────────────────────────────

export async function startFuturesSwingTrading(strategies, capital, scanIntervalMinutes = 240) {
  return apiFetch(`${API_BASE}/futures/swing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital, scan_interval_minutes: scanIntervalMinutes }),
  })
}

export async function stopFuturesSwingTrading() {
  return apiFetch(`${API_BASE}/futures/swing/stop`, { method: 'POST' })
}

export async function getFuturesSwingStatus() {
  return apiFetch(`${API_BASE}/futures/swing/status`)
}

// ── Futures Swing Paper Trading (Virtual) ─────────────────────

export async function startFuturesSwingPaperTrading(strategies, capital, scanIntervalMinutes = 240) {
  return apiFetch(`${API_BASE}/futures/swing-paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital, scan_interval_minutes: scanIntervalMinutes }),
  })
}

export async function stopFuturesSwingPaperTrading() {
  return apiFetch(`${API_BASE}/futures/swing-paper/stop`, { method: 'POST' })
}

export async function getFuturesSwingPaperStatus() {
  return apiFetch(`${API_BASE}/futures/swing-paper/status`)
}
