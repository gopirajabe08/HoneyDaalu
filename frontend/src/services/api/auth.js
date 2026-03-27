/**
 * Authentication endpoints — OTP request, OTP verify, auth status.
 */

import { API_BASE, apiFetch, setAuthToken, clearAuthToken, getAuthToken } from './base'

/**
 * Request an OTP for the given email. OTP is sent via Telegram.
 * @param {string} email
 * @returns {Promise<{status: string} | {error: string}>}
 */
export async function requestOTP(email) {
  // This endpoint doesn't need auth token — direct fetch
  const res = await fetch(`${API_BASE}/auth/request-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Request failed: ${res.status}`)
  }
  return res.json()
}

/**
 * Verify OTP and get a JWT token.
 * @param {string} email
 * @param {string} otp
 * @returns {Promise<{token: string, email: string} | {error: string}>}
 */
export async function verifyOTP(email, otp) {
  // This endpoint doesn't need auth token — direct fetch
  const res = await fetch(`${API_BASE}/auth/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Request failed: ${res.status}`)
  }
  const data = await res.json()

  // If token received, store it
  if (data.token) {
    setAuthToken(data.token)
  }

  return data
}

/**
 * Check if the stored token is still valid.
 * @returns {Promise<{authenticated: boolean, email?: string}>}
 */
export async function checkAuthStatus() {
  const token = getAuthToken()
  if (!token) {
    return { authenticated: false }
  }

  try {
    const res = await fetch(`${API_BASE}/auth/status`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (!res.ok) {
      clearAuthToken()
      return { authenticated: false }
    }
    const data = await res.json()
    if (!data.authenticated) {
      clearAuthToken()
    }
    return data
  } catch {
    return { authenticated: false }
  }
}

/**
 * Log out — clear the stored token.
 */
export function logout() {
  clearAuthToken()
  window.dispatchEvent(new CustomEvent('auth:logout'))
}
