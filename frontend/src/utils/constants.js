/**
 * Shared constants for LuckyNavi frontend.
 *
 * Centralizes values that were previously duplicated across
 * 7+ trading components (LOG_COLORS, CONVICTION_COLORS, etc.)
 */

/** Color classes for live log entries — maps log level to Tailwind text color */
export const LOG_COLORS = {
  START: 'text-green-400',
  STOP: 'text-red-400',
  SCAN: 'text-blue-400',
  ORDER: 'text-emerald-400',
  SQUAREOFF: 'text-purple-400',
  ALERT: 'text-yellow-400',
  ERROR: 'text-red-400',
  WARN: 'text-yellow-400',
  SKIP: 'text-gray-500',
  INFO: 'text-gray-400',
  RESTORE: 'text-cyan-400',
  REGIME: 'text-violet-400',
  EXPIRY: 'text-amber-400',
}

/** Market regime conviction → badge color (keys match backend snake_case) */
export const CONVICTION_COLORS = {
  'strongly_bullish': 'bg-green-500/15 text-green-400',
  'mildly_bullish': 'bg-emerald-500/15 text-emerald-400',
  'neutral': 'bg-violet-500/15 text-violet-400',
  'mildly_bearish': 'bg-emerald-500/15 text-emerald-400',
  'strongly_bearish': 'bg-red-500/15 text-red-400',
  'high_volatility': 'bg-yellow-500/15 text-yellow-400',
}

/** Market regime conviction → human-readable label */
export const CONVICTION_LABELS = {
  'strongly_bullish': 'Strongly Bullish',
  'mildly_bullish': 'Mildly Bullish',
  'neutral': 'Neutral / Range',
  'mildly_bearish': 'Mildly Bearish',
  'strongly_bearish': 'Strongly Bearish',
  'high_volatility': 'High Volatility',
}

/** Underlying options for options trading */
export const UNDERLYING_OPTIONS = ['NIFTY', 'BANKNIFTY']
