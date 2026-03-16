import { getApiBase, apiFetch } from './base'

const api = () => getApiBase()

export const getFuturesStrategies = () => apiFetch(`${api()}/futures/strategies`)
export const getFuturesOI = (symbol) => apiFetch(`${api()}/futures/oi/${symbol}`)

// Futures Auto (Intraday Live)
export const startFuturesAutoTrading = (strategies, capital) =>
  apiFetch(`${api()}/futures/auto/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital }) })
export const stopFuturesAutoTrading = () => apiFetch(`${api()}/futures/auto/stop`, { method: 'POST' })
export const getFuturesAutoStatus = () => apiFetch(`${api()}/futures/auto/status`)

// Futures Paper (Intraday)
export const startFuturesPaperTrading = (strategies, capital) =>
  apiFetch(`${api()}/futures/paper/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital }) })
export const stopFuturesPaperTrading = () => apiFetch(`${api()}/futures/paper/stop`, { method: 'POST' })
export const getFuturesPaperStatus = () => apiFetch(`${api()}/futures/paper/status`)

// Futures Swing (Live)
export const startFuturesSwingTrading = (strategies, capital, scanIntervalMinutes = 240) =>
  apiFetch(`${api()}/futures/swing/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital, scan_interval_minutes: scanIntervalMinutes }) })
export const stopFuturesSwingTrading = () => apiFetch(`${api()}/futures/swing/stop`, { method: 'POST' })
export const getFuturesSwingStatus = () => apiFetch(`${api()}/futures/swing/status`)

// Futures Swing Paper
export const startFuturesSwingPaperTrading = (strategies, capital, scanIntervalMinutes = 240) =>
  apiFetch(`${api()}/futures/swing-paper/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategies, capital, scan_interval_minutes: scanIntervalMinutes }) })
export const stopFuturesSwingPaperTrading = () => apiFetch(`${api()}/futures/swing-paper/stop`, { method: 'POST' })
export const getFuturesSwingPaperStatus = () => apiFetch(`${api()}/futures/swing-paper/status`)
