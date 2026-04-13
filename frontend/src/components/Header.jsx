import React, { useState, useEffect, useRef } from 'react'
import { Clock, CalendarOff, ChevronDown, Link2, Link2Off, Wallet, ClipboardPaste, Loader2, X } from 'lucide-react'
import { getMarketStatus, getBrokerFunds, getBrokerLoginUrl, brokerVerifyAuthCode, getBrokerStatus, brokerLogout } from '../services/api'

export default function Header({ brokerStatus }) {
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
    if (brokerStatus?.connected) {
      getBrokerFunds().then(setFunds).catch(() => setFunds(null))
      const iv = setInterval(() => { getBrokerFunds().then(setFunds).catch(() => setFunds(null)) }, 30000)
      return () => clearInterval(iv)
    }
  }, [brokerStatus?.connected])

  async function checkMarket() {
    try { setMarketStatus(await getMarketStatus()) } catch {}
  }

  async function handleConnect() {
    setConnectError('')
    try {
      const data = await getBrokerLoginUrl()
      if (data.auth_url) {
        window.open(data.auth_url, 'tradejini_login', 'width=600,height=700')
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
      const result = await brokerVerifyAuthCode(code)
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

  const profileName = brokerStatus?.profile?.name || 'Trader'
  const upcomingHolidays = marketStatus?.upcoming_holidays || []
  const nextTradingDay = marketStatus?.next_trading_day || ''

  const available = funds?.fund_limit?.find(f => f.title === 'Available Balance')?.equityAmount || 0
  const total = funds?.fund_limit?.find(f => f.title === 'Total Balance')?.equityAmount || 0
  const used = total - available

  const formatINR = (v) => `\u20B9${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`

  return (
    <header
      className="flex items-center justify-between px-6 py-3 theme-transition"
      style={{ backgroundColor: 'var(--header-bg)', borderBottom: '1px solid var(--border)' }}
    >
      {/* Left - Brand */}
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-[10px] shadow-md"
          style={{ background: 'linear-gradient(135deg, var(--gradient-start), var(--gradient-end))', boxShadow: '0 2px 10px var(--accent-glow)' }}
        >
          LN
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-gradient">LuckyNavi</h1>
          <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>Algo Trading</p>
        </div>
      </div>

      {/* Center - Market status + Clock */}
      <div className="flex items-center gap-3">
        {marketStatus && (
          <div className="relative">
            <button
              onClick={() => setShowHolidays(!showHolidays)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] font-medium cursor-pointer"
              style={{
                backgroundColor: marketStatus.is_open ? 'var(--positive-light)' : 'var(--bg-tertiary)',
                color: marketStatus.is_open ? 'var(--positive)' : 'var(--text-secondary)',
                border: `1px solid ${marketStatus.is_open ? 'transparent' : 'var(--border)'}`,
              }}
            >
              <div className={`w-1.5 h-1.5 rounded-full ${marketStatus.is_open ? 'bg-green-400 animate-pulse' : ''}`} style={!marketStatus.is_open ? { backgroundColor: 'var(--text-muted)' } : {}} />
              {marketStatus.message}
              {upcomingHolidays.length > 0 && <ChevronDown size={11} className={`transition-transform ${showHolidays ? 'rotate-180' : ''}`} />}
            </button>

            {showHolidays && upcomingHolidays.length > 0 && (
              <div
                className="absolute top-full mt-2 left-1/2 -translate-x-1/2 z-50 rounded-xl shadow-2xl p-3 min-w-[240px]"
                style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
              >
                {!marketStatus.is_open && nextTradingDay && (
                  <div className="flex items-center gap-2 text-[11px] mb-2 pb-2" style={{ color: 'var(--positive)', borderBottom: '1px solid var(--border)' }}>
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--positive)' }} />
                    Next trading day: {nextTradingDay}
                  </div>
                )}
                <p className="text-[9px] uppercase tracking-wider mb-1.5 flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
                  <CalendarOff size={9} /> Upcoming Holidays
                </p>
                {upcomingHolidays.map((h, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 py-1 text-[11px]">
                    <span style={{ color: 'var(--text-primary)' }}>{h.name}</span>
                    <span className="text-[9px] whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>{h.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg" style={{ backgroundColor: 'var(--bg-tertiary)' }}>
          <Clock size={11} style={{ color: 'var(--text-muted)' }} />
          <span className="text-[11px] tabular-nums font-mono" style={{ color: 'var(--text-secondary)' }}>{time}</span>
          <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>IST</span>
        </div>
      </div>

      {/* Right - Funds + Connection */}
      <div className="flex items-center gap-3">
        {brokerStatus?.connected ? (
          <>
            {funds && (
              <div
                className="flex items-center gap-3 rounded-xl px-3 py-2"
                style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
              >
                <Wallet size={13} style={{ color: 'var(--accent)' }} />
                <div className="flex items-center gap-4 text-[10px]">
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Available </span>
                    <span style={{ color: 'var(--positive)' }} className="font-semibold">{formatINR(available)}</span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Used </span>
                    <span style={{ color: 'var(--accent)' }} className="font-semibold">{formatINR(used)}</span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Total </span>
                    <span style={{ color: 'var(--text-primary)' }} className="font-semibold">{formatINR(total)}</span>
                  </div>
                </div>
              </div>
            )}

            <div
              className="flex items-center gap-2 rounded-xl px-3 py-2"
              style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-[10px] font-bold"
                style={{ background: 'linear-gradient(135deg, var(--gradient-start), var(--gradient-end))' }}
              >
                {profileName.charAt(0)}
              </div>
              <span className="text-[11px] font-medium" style={{ color: 'var(--text-primary)' }}>{profileName}</span>
              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--positive)' }} />
              <button
                onClick={() => { brokerLogout(); window.location.reload() }}
                className="ml-1 transition-colors"
                style={{ color: 'var(--text-muted)' }}
                title="Disconnect TradeJini"
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--negative)' }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
              >
                <Link2Off size={13} />
              </button>
            </div>
          </>
        ) : (
          <div className="flex items-center gap-2">
            {connectStep === 'idle' && (
              <button
                onClick={handleConnect}
                className="flex items-center gap-2 text-white rounded-xl px-4 py-2 text-[11px] font-semibold hover:opacity-90 transition-opacity shadow-lg"
                style={{ background: 'linear-gradient(135deg, var(--gradient-start), var(--gradient-end))', boxShadow: '0 4px 15px var(--accent-glow)' }}
              >
                <Link2 size={13} />
                Connect TradeJini
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
                    className="rounded-xl pl-3 pr-20 py-2 text-[11px] focus:outline-none w-[280px]"
                    style={{
                      backgroundColor: 'var(--bg-tertiary)',
                      border: '1px solid var(--border)',
                      color: 'var(--text-primary)',
                    }}
                  />
                  <button
                    onClick={handlePasteSubmit}
                    disabled={!pasteUrl.trim()}
                    className="absolute right-1 top-1 px-2.5 py-1 text-white rounded-lg text-[10px] font-semibold flex items-center gap-1 hover:opacity-90 disabled:opacity-30"
                    style={{ background: 'linear-gradient(135deg, var(--gradient-start), var(--gradient-end))' }}
                  >
                    <ClipboardPaste size={10} /> Connect
                  </button>
                </div>
                <button onClick={() => { setConnectStep('idle'); setPasteUrl(''); setConnectError('') }} style={{ color: 'var(--text-secondary)' }} className="hover:text-red-400">
                  <X size={13} />
                </button>
              </div>
            )}

            {connectStep === 'verifying' && (
              <div className="flex items-center gap-2 text-[11px]" style={{ color: 'var(--text-primary)' }}>
                <Loader2 size={13} className="animate-spin" style={{ color: 'var(--accent)' }} />
                Verifying...
              </div>
            )}

            {connectError && (
              <span className="text-[10px] max-w-[200px] truncate" style={{ color: 'var(--negative)' }}>{connectError}</span>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
