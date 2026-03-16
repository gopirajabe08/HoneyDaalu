import AsyncStorage from '@react-native-async-storage/async-storage'

const STORAGE_KEY = '@intratrading_server_ip'
const DEFAULT_IP = '192.168.0.104'
const PORT = '8001'

let _cachedBase = null

export function getApiBase() {
  if (_cachedBase) return _cachedBase
  return `http://${DEFAULT_IP}:${PORT}/api`
}

export function setApiBase(ip) {
  _cachedBase = `http://${ip}:${PORT}/api`
}

export async function loadSavedIp() {
  try {
    const ip = await AsyncStorage.getItem(STORAGE_KEY)
    if (ip) {
      _cachedBase = `http://${ip}:${PORT}/api`
      return ip
    }
  } catch {}
  return DEFAULT_IP
}

export async function saveServerIp(ip) {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, ip)
    _cachedBase = `http://${ip}:${PORT}/api`
  } catch {}
}

export async function apiFetch(url, options) {
  const res = await fetch(url, { ...options, timeout: 15000 })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Request failed: ${res.status}`)
  }
  return res.json()
}
