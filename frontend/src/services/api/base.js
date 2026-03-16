/**
 * Shared API base URL and fetch helper.
 */

export const API_BASE = 'http://localhost:8001/api'

/**
 * Wrapper around fetch that throws on non-OK responses.
 *
 * @param {string} url - Full URL to fetch
 * @param {RequestInit} [options] - Fetch options (method, headers, body, etc.)
 * @returns {Promise<any>} Parsed JSON response
 */
export async function apiFetch(url, options) {
  const res = await fetch(url, options)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Request failed: ${res.status}`)
  }
  return res.json()
}
