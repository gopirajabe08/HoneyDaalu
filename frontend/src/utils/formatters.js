/**
 * Shared formatting functions for IntraTrading frontend.
 *
 * Centralizes currency formatting and other display helpers
 * that were previously duplicated across 8+ components.
 */

/**
 * Format a number as Indian Rupees with 2 decimal places.
 * Always returns the absolute value (use sign prefix separately).
 *
 * @param {number} value - Amount to format
 * @returns {string} e.g. "₹1,23,456.78"
 */
export function formatINR(value) {
  return `₹${Math.abs(value ?? 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/**
 * Format a number as Indian Rupees with no decimal places.
 * Used in dashboard, specialist views, and stat cards.
 *
 * @param {number} value - Amount to format
 * @returns {string} e.g. "₹1,23,457"
 */
export function formatINRCompact(value) {
  return `₹${Math.abs(value ?? 0).toLocaleString('en-IN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`
}

/**
 * Format options spread legs for display.
 * Handles both numeric side (1/-1) and string side ('BUY'/'SELL').
 *
 * @param {Array} legs - Array of leg objects with {side, strike, option_type}
 * @returns {string} e.g. "BUY 22500CE + SELL 22400PE"
 */
export function formatLegs(legs) {
  if (!legs || legs.length === 0) return '--'
  return legs.map(l => {
    const side = l.side === 1 ? 'BUY' : l.side === -1 ? 'SELL' : (l.side || '?')
    return `${side} ${l.strike}${l.option_type}`
  }).join(' + ')
}
