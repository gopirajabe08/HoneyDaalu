/**
 * Shared API base URL, fetch helper, and auth utilities.
 */

// Use relative URL — works on both localhost (via Vite proxy) and cloud (via Nginx proxy)
export const API_BASE = '/api'

/**
 * Get the stored auth token from localStorage.
 */
export function getAuthToken() {
  return localStorage.getItem('luckynavi_token')
}

/**
 * Set the auth token in localStorage.
 */
export function setAuthToken(token) {
  localStorage.setItem('luckynavi_token', token)
}

/**
 * Clear the auth token from localStorage.
 */
export function clearAuthToken() {
  localStorage.removeItem('luckynavi_token')
}

/**
 * Wrapper around fetch that:
 * - Adds Authorization header with JWT token
 * - Throws on non-OK responses
 * - Clears token and dispatches event on 401 (forces re-login)
 *
 * @param {string} url - Full URL to fetch
 * @param {RequestInit} [options] - Fetch options (method, headers, body, etc.)
 * @returns {Promise<any>} Parsed JSON response
 */
export async function apiFetch(url, options = {}) {
  const token = getAuthToken()

  // Merge auth header into options
  const headers = { ...(options.headers || {}) }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(url, { ...options, headers })

  // Handle 401 — token expired or invalid
  if (res.status === 401) {
    clearAuthToken()
    // Dispatch custom event so App.jsx can react
    window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Request failed: ${res.status}`)
  }

  return res.json()
}
