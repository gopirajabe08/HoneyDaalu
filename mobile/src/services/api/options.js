import { getApiBase, apiFetch } from './base'

const api = () => getApiBase()

export const getMarketRegime = () => apiFetch(`${api()}/options/regime`)
export const getOptionsStrategies = () => apiFetch(`${api()}/options/strategies`)
export const getOptionChain = (underlying) => apiFetch(`${api()}/options/chain/${underlying}`)
export const scanOptions = (underlying, capital = 200000, mode = 'intraday') =>
  apiFetch(`${api()}/options/scan/${underlying}?capital=${capital}&mode=${mode}`)

// Options Auto (Intraday Live)
export const startOptionsAutoTrading = (capital, underlyings) =>
  apiFetch(`${api()}/options/auto/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capital, underlyings }) })
export const stopOptionsAutoTrading = () => apiFetch(`${api()}/options/auto/stop`, { method: 'POST' })
export const getOptionsAutoStatus = () => apiFetch(`${api()}/options/auto/status`)

// Options Paper (Intraday)
export const startOptionsPaperTrading = (capital, underlyings) =>
  apiFetch(`${api()}/options/paper/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capital, underlyings }) })
export const stopOptionsPaperTrading = () => apiFetch(`${api()}/options/paper/stop`, { method: 'POST' })
export const getOptionsPaperStatus = () => apiFetch(`${api()}/options/paper/status`)

// Options Swing (Live)
export const startOptionsSwingTrading = (capital, underlyings) =>
  apiFetch(`${api()}/options/swing/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capital, underlyings }) })
export const stopOptionsSwingTrading = () => apiFetch(`${api()}/options/swing/stop`, { method: 'POST' })
export const getOptionsSwingStatus = () => apiFetch(`${api()}/options/swing/status`)

// Options Swing Paper
export const startOptionsSwingPaperTrading = (capital, underlyings) =>
  apiFetch(`${api()}/options/swing-paper/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capital, underlyings }) })
export const stopOptionsSwingPaperTrading = () => apiFetch(`${api()}/options/swing-paper/stop`, { method: 'POST' })
export const getOptionsSwingPaperStatus = () => apiFetch(`${api()}/options/swing-paper/status`)
