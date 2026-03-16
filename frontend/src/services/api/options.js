/**
 * Options trading endpoints — strategies, regime, scan, chain,
 * and all four trader controls (auto/paper x intraday/swing).
 */

import { API_BASE, apiFetch } from './base'

// ── Options Strategies & Data ─────────────────────────────────

export async function getOptionsStrategies() {
  return apiFetch(`${API_BASE}/options/strategies`)
}

export async function getMarketRegime(underlying = 'NIFTY') {
  return apiFetch(`${API_BASE}/options/regime?underlying=${underlying}`)
}

export async function scanOptions(underlying, capital = 200000, mode = 'intraday') {
  const params = new URLSearchParams({ capital, mode })
  return apiFetch(`${API_BASE}/options/scan/${underlying}?${params}`)
}

export async function getOptionChain(underlying, expiry = 'weekly') {
  return apiFetch(`${API_BASE}/options/chain/${underlying}?expiry=${expiry}`)
}

// ── Options Auto-Trading (Intraday Live) ──────────────────────

export async function startOptionsAutoTrading(capital, underlyings = ['NIFTY', 'BANKNIFTY']) {
  return apiFetch(`${API_BASE}/options/auto/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital, underlyings }),
  })
}

export async function stopOptionsAutoTrading() {
  return apiFetch(`${API_BASE}/options/auto/stop`, { method: 'POST' })
}

export async function getOptionsAutoStatus() {
  return apiFetch(`${API_BASE}/options/auto/status`)
}

// ── Options Paper Trading (Intraday) ──────────────────────────

export async function startOptionsPaperTrading(capital, underlyings = ['NIFTY', 'BANKNIFTY']) {
  return apiFetch(`${API_BASE}/options/paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital, underlyings }),
  })
}

export async function stopOptionsPaperTrading() {
  return apiFetch(`${API_BASE}/options/paper/stop`, { method: 'POST' })
}

export async function getOptionsPaperStatus() {
  return apiFetch(`${API_BASE}/options/paper/status`)
}

// ── Options Swing Trading (Live) ──────────────────────────────

export async function startOptionsSwingTrading(capital, underlyings = ['NIFTY', 'BANKNIFTY']) {
  return apiFetch(`${API_BASE}/options/swing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital, underlyings }),
  })
}

export async function stopOptionsSwingTrading() {
  return apiFetch(`${API_BASE}/options/swing/stop`, { method: 'POST' })
}

export async function getOptionsSwingStatus() {
  return apiFetch(`${API_BASE}/options/swing/status`)
}

// ── Options Swing Paper Trading ───────────────────────────────

export async function startOptionsSwingPaperTrading(capital, underlyings = ['NIFTY', 'BANKNIFTY']) {
  return apiFetch(`${API_BASE}/options/swing-paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital, underlyings }),
  })
}

export async function stopOptionsSwingPaperTrading() {
  return apiFetch(`${API_BASE}/options/swing-paper/stop`, { method: 'POST' })
}

export async function getOptionsSwingPaperStatus() {
  return apiFetch(`${API_BASE}/options/swing-paper/status`)
}
