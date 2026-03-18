import React, { useState, useEffect, useRef } from 'react'
import { Clock, CalendarOff, ChevronDown, Link2, Link2Off, Wallet, ClipboardPaste, Loader2, X } from 'lucide-react'
import { getMarketStatus, getFyersFunds, getFyersLoginUrl, fyersVerifyAuthCode, getFyersStatus, fyersLogout } from '../services/api'

export default function Header({ fyersStatus }) {
  const [marketStatus, setMarketStatus] = useState(null)
  const [time, setTime] = useState('')
  const [showHolidays, setShowHolidays] = useState(false)
  const [funds, setFunds] = useState(null)
  const [connectStep, setConnectStep] = useState('idle') // idle | waiting | verifying
  const [pasteUrl, setPasteUrl] = useState('')
  const [connectError, setConnectError] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    checkMarket()
    const marketInterval = setInterval(checkMarket, 60000)
    const clockInterval = setInterval(() => {
      setTime(new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }, 1000)
    return () => { clearInterval(marketInterval); clearInterval(clockInterval) }
  }, [])

  // Fetch funds when connected
  useEffect(() => {
    if (fyersStatus?.connected) {
      getFyersFunds().then(setFunds).catch(() => {})
      const iv = setInterval(() => { getFyersFunds().then(setFunds).catch(() => {}) }, 30000)
      return () => clearInterval(iv)
    }
  }, [fyersStatus?.connected])

  async function checkMarket() {
    try { setMarketStatus(await getMarketStatus()) } catch {}
  }

  async function handleConnect() {
    setConnectError('')
    try {
      const data = await getFyersLoginUrl()
      if (data.auth_url) {
        window.open(data.auth_url, 'fyers_login', 'width=600,height=700')
        setConnectStep('waiting')
        setTimeout(() => inputRef.current?.focus(), 300)
      } else {
        setConnectError(data.error || 'Failed to get login URL')
      }
    } catch (e) {
      setConnectError(e.message)
    }
  }

  function extractAuthCode(input) {
    const trimmed = input.trim()
    const match = trimmed.match(/auth_code=([^&]+)/)
    if (match) return match[1]
    if (trimmed.length > 10 && !trimmed.includes(' ')) return trimmed
    return null
  }

  async function handlePasteSubmit() {
    const code = extractAuthCode(pasteUrl)
    if (!code) {
      setConnectError('Could not find auth code. Copy the full URL from the login window.')
      return
    }
    setConnectStep('verifying')
    setConnectError('')
    try {
      const result = await fyersVerifyAuthCode(code)
      if (result.status === 'ok') {
        setPasteUrl('')
        setConnectStep('idle')
        // Refresh status
        window.location.reload()
      } else {
        setConnectError(result.error || 'Verification failed')
        setConnectStep('waiting')
      }
    } catch (e) {
      setConnectError(e.message)
      setConnectStep('waiting')
    }
  }

  function handleInputChange(e) {
    const val = e.target.value
    setPasteUrl(val)
    if (val.includes('auth_code=')) {
      setTimeout(() => {
        const code = extractAuthCode(val)
        if (code) handlePasteSubmit()
      }, 200)
    }
  }

  const profileName = fyersStatus?.profile?.name || 'Trader'
  const upcomingHolidays = marketStatus?.upcoming_holidays || []
  const nextTradingDay = marketStatus?.next_trading_day || ''

  const available = funds?.fund_limit?.find(f => f.title === 'Available Balance')?.equityAmount || 0
  const total = funds?.fund_limit?.find(f => f.title === 'Total Balance')?.equityAmount || 0
  const used = total - available

  const formatINR = (v) => `\u20B9${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`

  return (
    <header className="flex items-center justify-between px-6 py-4">
      {/* Left - Brand */}
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-pink-400">Intra</span>
          <span className="text-white">Trading</span>
        </h1>
      </div>

      {/* Center - Market status + Clock + Holidays */}
      <div className="flex items-center gap-4">
        {marketStatus && (
          <div className="relative">
            <button
              onClick={() => setShowHolidays(!showHolidays)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer ${
                marketStatus.is_open
                  ? 'bg-green-500/10 text-green-400'
                  : 'bg-dark-700 text-gray-400 border border-dark-500'
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${marketStatus.is_open ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
              {marketStatus.message}
              {upcomingHolidays.length > 0 && <ChevronDown size={12} className={`transition-transform ${showHolidays ? 'rotate-180' : ''}`} />}
            </button>

            {showHolidays && upcomingHolidays.length > 0 && (
              <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 z-50 bg-dark-700 border border-dark-500 rounded-xl shadow-xl p-3 min-w-[240px]">
                {!marketStatus.is_open && nextTradingDay && (
                  <div className="flex items-center gap-2 text-xs text-green-400 mb-2 pb-2 border-b border-dark-500">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
                    Next trading day: {nextTradingDay}
                  </div>
                )}
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <CalendarOff size={10} /> Upcoming Holidays
                </p>
                {upcomingHolidays.map((h, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 py-1 text-xs">
                    <span className="text-gray-300">{h.name}</span>
                    <span className="text-gray-500 text-[10px] whitespace-nowrap">{h.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-1.5 text-gray-400">
          <Clock size={13} />
          <span className="text-xs tabular-nums font-mono">{time}</span>
          <span className="text-[10px] text-gray-500">IST</span>
        </div>
      </div>

      {/* Right - Funds + Connection */}
      <div className="flex items-center gap-3">
        {fyersStatus?.connected ? (
          <>
            {/* Balance display */}
            {funds && (
              <div className="flex items-center gap-3 bg-dark-700 border border-dark-500 rounded-xl px-3 py-2">
                <Wallet size={14} className="text-yellow-400" />
                <div className="flex items-center gap-4 text-[10px]">
                  <div>
                    <span className="text-gray-500">Available </span>
                    <span className="text-green-400 font-semibold">{formatINR(available)}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Used </span>
                    <span className="text-orange-400 font-semibold">{formatINR(used)}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Total </span>
                    <span className="text-white font-semibold">{formatINR(total)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Profile badge + disconnect */}
            <div className="flex items-center gap-2 bg-dark-700 border border-dark-500 rounded-xl px-3 py-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center text-white text-[10px] font-bold">
                {profileName.charAt(0)}
              </div>
              <span className="text-xs text-white font-medium">{profileName}</span>
              <div className="w-2 h-2 rounded-full bg-green-400" />
              <button
                onClick={() => { fyersLogout(); window.location.reload() }}
                className="ml-1 text-gray-500 hover:text-red-400 transition-colors"
                title="Disconnect Fyers"
              >
                <Link2Off size={14} />
              </button>
            </div>
          </>
        ) : (
          <div className="flex items-center gap-2">
            {connectStep === 'idle' && (
              <button
                onClick={handleConnect}
                className="flex items-center gap-2 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-xl px-4 py-2 text-xs font-semibold hover:opacity-90 transition-opacity"
              >
                <Link2 size={14} />
                Connect Fyers
              </button>
            )}

            {connectStep === 'waiting' && (
              <div className="flex items-center gap-2">
                <div className="relative">
                  <input
                    ref={inputRef}
                    type="text"
                    value={pasteUrl}
                    onChange={handleInputChange}
                    placeholder="Paste login URL here..."
                    className="bg-dark-800 border border-dark-500 rounded-xl pl-3 pr-20 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 w-[280px]"
                  />
                  <button
                    onClick={handlePasteSubmit}
                    disabled={!pasteUrl.trim()}
                    className="absolute right-1 top-1 px-2.5 py-1 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg text-[10px] font-semibold flex items-center gap-1 hover:opacity-90 disabled:opacity-30"
                  >
                    <ClipboardPaste size={10} /> Connect
                  </button>
                </div>
                <button onClick={() => { setConnectStep('idle'); setPasteUrl(''); setConnectError('') }} className="text-gray-500 hover:text-red-400">
                  <X size={14} />
                </button>
              </div>
            )}

            {connectStep === 'verifying' && (
              <div className="flex items-center gap-2 text-xs text-gray-300">
                <Loader2 size={14} className="text-green-400 animate-spin" />
                Verifying...
              </div>
            )}

            {connectError && (
              <span className="text-[10px] text-red-400 max-w-[200px] truncate">{connectError}</span>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
