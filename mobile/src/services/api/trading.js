import { getApiBase, apiFetch } from './base'

const api = () => getApiBase()

// Auto-Trading (Intraday Live)
export const startAutoTrading = (strategies, capital) =>
  apiFetch(`${api()}/auto/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital }) })
export const stopAutoTrading = () => apiFetch(`${api()}/auto/stop`, { method: 'POST' })
export const getAutoStatus = () => apiFetch(`${api()}/auto/status`)

// Paper Trading (Intraday)
export const startPaperTrading = (strategies, capital) =>
  apiFetch(`${api()}/paper/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital }) })
export const stopPaperTrading = () => apiFetch(`${api()}/paper/stop`, { method: 'POST' })
export const getPaperStatus = () => apiFetch(`${api()}/paper/status`)

// Swing Trading (Live)
export const startSwingTrading = (strategies, capital) =>
  apiFetch(`${api()}/swing/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital }) })
export const stopSwingTrading = () => apiFetch(`${api()}/swing/stop`, { method: 'POST' })
export const getSwingStatus = () => apiFetch(`${api()}/swing/status`)

// Swing Paper Trading
export const startSwingPaperTrading = (strategies, capital) =>
  apiFetch(`${api()}/swing-paper/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital }) })
export const stopSwingPaperTrading = () => apiFetch(`${api()}/swing-paper/stop`, { method: 'POST' })
export const getSwingPaperStatus = () => apiFetch(`${api()}/swing-paper/status`)

// Strategy Stats & Trade History
export const getStrategyStats = (source) => apiFetch(`${api()}/strategy/stats${source ? `?source=${source}` : ''}`)
export const getTradeHistory = (days = 30, source) => {
  const p = new URLSearchParams({ days })
  if (source) p.append('source', source)
  return apiFetch(`${api()}/trades/history?${p}`)
}
export const getDailyPnl = (days = 30, source) => {
  const p = new URLSearchParams({ days })
  if (source) p.append('source', source)
  return apiFetch(`${api()}/trades/daily-pnl?${p}`)
}
