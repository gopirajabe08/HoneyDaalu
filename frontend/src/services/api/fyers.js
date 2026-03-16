/**
 * Fyers authentication, account, orders, positions, and market data endpoints.
 */

import { API_BASE, apiFetch } from './base'

// ── Auth ──────────────────────────────────────────────────────

export async function getFyersStatus() {
  return apiFetch(`${API_BASE}/fyers/status`)
}

export async function getFyersLoginUrl() {
  return apiFetch(`${API_BASE}/fyers/login`)
}

export async function fyersLogout() {
  return apiFetch(`${API_BASE}/fyers/logout`, { method: 'POST' })
}

export async function fyersVerifyAuthCode(authCode) {
  return apiFetch(`${API_BASE}/fyers/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auth_code: authCode }),
  })
}

// ── Account ───────────────────────────────────────────────────

export async function getFyersFunds() {
  return apiFetch(`${API_BASE}/fyers/funds`)
}

export async function getFyersProfile() {
  return apiFetch(`${API_BASE}/fyers/profile`)
}

// ── Orders ────────────────────────────────────────────────────

export async function placeOrder(orderData) {
  return apiFetch(`${API_BASE}/fyers/order`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(orderData),
  })
}

export async function placeBracketOrder(orderData) {
  return apiFetch(`${API_BASE}/fyers/order/bracket`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(orderData),
  })
}

export async function cancelOrder(orderId) {
  return apiFetch(`${API_BASE}/fyers/order/${orderId}`, { method: 'DELETE' })
}

export async function getOrderbook() {
  return apiFetch(`${API_BASE}/fyers/orders`)
}

// ── Positions ─────────────────────────────────────────────────

export async function getPositions() {
  return apiFetch(`${API_BASE}/fyers/positions`)
}

export async function getHoldings() {
  return apiFetch(`${API_BASE}/fyers/holdings`)
}

// ── Market Data ───────────────────────────────────────────────

export async function getQuotes(symbols) {
  return apiFetch(`${API_BASE}/fyers/quotes?symbols=${symbols.join(',')}`)
}
