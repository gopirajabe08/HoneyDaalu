import { getApiBase, apiFetch } from './base'

const api = () => getApiBase()

export const getMarketStatus = () => apiFetch(`${api()}/market/status`)
export const fetchStrategies = () => apiFetch(`${api()}/strategies`)

// Capital Tracking
export const setInitialCapital = (amount, source = 'live') =>
  apiFetch(`${api()}/capital/set`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount, source }) })
export const addCapitalTransaction = (amount, type, source = 'live', note = '') =>
  apiFetch(`${api()}/capital/transaction`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount, type, source, note }) })
export const getCapitalInfo = (source = 'live') => apiFetch(`${api()}/capital/info?source=${source}`)
export const deleteCapitalTransaction = (index, source = 'live') =>
  apiFetch(`${api()}/capital/transaction/${index}?source=${source}`, { method: 'DELETE' })
