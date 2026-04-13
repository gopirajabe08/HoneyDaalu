/**
 * Broker (TradeJini) authentication, account, orders, positions, and market data endpoints.
 */

import { API_BASE, apiFetch } from './base'

// -- Auth ------------------------------------------------------------------

export async function getBrokerStatus() {
  return apiFetch(`${API_BASE}/broker/status`)
}

export async function getBrokerLoginUrl() {
  return apiFetch(`${API_BASE}/broker/login`)
}

export async function brokerLogout() {
  return apiFetch(`${API_BASE}/broker/logout`, { method: 'POST' })
}

export async function brokerVerifyAuthCode(authCode) {
  return apiFetch(`${API_BASE}/broker/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auth_code: authCode }),
  })
}

// -- Account ---------------------------------------------------------------

export async function getBrokerFunds() {
  return apiFetch(`${API_BASE}/broker/funds`)
}

export async function getBrokerProfile() {
  return apiFetch(`${API_BASE}/broker/profile`)
}

// -- Orders ----------------------------------------------------------------

export async function placeOrder(orderData) {
  return apiFetch(`${API_BASE}/broker/order`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(orderData),
  })
}

export async function placeBracketOrder(orderData) {
  return apiFetch(`${API_BASE}/broker/order/bracket`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(orderData),
  })
}

export async function cancelOrder(orderId) {
  return apiFetch(`${API_BASE}/broker/order/${orderId}`, { method: 'DELETE' })
}

export async function getOrderbook() {
  return apiFetch(`${API_BASE}/broker/orders`)
}

// -- Positions -------------------------------------------------------------

export async function getPositions() {
  return apiFetch(`${API_BASE}/broker/positions`)
}

export async function getHoldings() {
  return apiFetch(`${API_BASE}/broker/holdings`)
}

// -- Market Data -----------------------------------------------------------

export async function getQuotes(symbols) {
  return apiFetch(`${API_BASE}/broker/quotes?symbols=${symbols.join(',')}`)
}
