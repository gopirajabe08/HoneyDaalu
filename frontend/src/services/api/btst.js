/**
 * BTST (Buy Today Sell Tomorrow) trading endpoints —
 * live and paper trader controls with regime auto-start.
 */

import { API_BASE, apiFetch } from './base'

// ── BTST Live Trading ─────────────────────────────────────────

export async function startBTST(strategies, capital) {
  return apiFetch(`${API_BASE}/btst/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital }),
  })
}

export async function stopBTST() {
  return apiFetch(`${API_BASE}/btst/stop`, { method: 'POST' })
}

export async function getBTSTStatus() {
  return apiFetch(`${API_BASE}/btst/status`)
}

export async function startBTSTRegime(capital) {
  return apiFetch(`${API_BASE}/btst/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}

// ── BTST Paper Trading ────────────────────────────────────────

export async function startBTSTPaper(strategies, capital) {
  return apiFetch(`${API_BASE}/btst-paper/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategies, capital }),
  })
}

export async function stopBTSTPaper() {
  return apiFetch(`${API_BASE}/btst-paper/stop`, { method: 'POST' })
}

export async function getBTSTPaperStatus() {
  return apiFetch(`${API_BASE}/btst-paper/status`)
}

export async function startBTSTPaperRegime(capital) {
  return apiFetch(`${API_BASE}/btst-paper/start-auto`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital }),
  })
}
