import { getApiBase, apiFetch } from './base'

const api = () => getApiBase()

export const getFyersStatus = () => apiFetch(`${api()}/fyers/status`)
export const getFyersLoginUrl = () => apiFetch(`${api()}/fyers/login`)
export const fyersLogout = () => apiFetch(`${api()}/fyers/logout`, { method: 'POST' })
export const getFyersFunds = () => apiFetch(`${api()}/fyers/funds`)
export const getFyersProfile = () => apiFetch(`${api()}/fyers/profile`)
export const getOrderbook = () => apiFetch(`${api()}/fyers/orders`)
export const getPositions = () => apiFetch(`${api()}/fyers/positions`)
export const getHoldings = () => apiFetch(`${api()}/fyers/holdings`)
