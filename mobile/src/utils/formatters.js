export function formatINR(value) {
  if (value === null || value === undefined) return '--'
  const num = Number(value)
  const sign = num >= 0 ? '+' : ''
  return `${sign}\u20B9${Math.round(num).toLocaleString('en-IN')}`
}

export function formatINRShort(value) {
  const num = Math.abs(Number(value))
  if (num >= 10000000) return `\u20B9${(num / 10000000).toFixed(1)}Cr`
  if (num >= 100000) return `\u20B9${(num / 100000).toFixed(1)}L`
  if (num >= 1000) return `\u20B9${(num / 1000).toFixed(1)}K`
  return `\u20B9${Math.round(num)}`
}

export function formatTime(isoString) {
  if (!isoString) return '--'
  try {
    const d = new Date(isoString)
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
  } catch { return '--' }
}

export function formatDate(dateStr) {
  if (!dateStr) return '--'
  const parts = dateStr.split('-')
  if (parts.length !== 3) return dateStr
  return `${parts[2]}/${parts[1]}`
}
