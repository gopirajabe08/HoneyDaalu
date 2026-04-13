import React, { useState, useEffect, useRef } from 'react'
import { Link2, Link2Off, User, LogOut, RefreshCw, ExternalLink, Loader2, ClipboardPaste } from 'lucide-react'
import { getBrokerStatus, getBrokerLoginUrl, brokerLogout, getBrokerFunds, brokerVerifyAuthCode } from '../services/api'

export default function BrokerConnect({ brokerStatus, setBrokerStatus }) {
  const [loading, setLoading] = useState(true)
  const [funds, setFunds] = useState(null)
  const [error, setError] = useState('')
  const [step, setStep] = useState('idle') // idle | waiting | verifying
  const [pastedUrl, setPastedUrl] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { checkStatus() }, [])

  async function checkStatus() {
    setLoading(true)
    try {
      const status = await getBrokerStatus()
      setBrokerStatus(status)
      if (status.connected) {
        setStep('idle')
        try { setFunds(await getBrokerFunds()) } catch {}
      }
    } catch {
      setBrokerStatus({ connected: false, configured: false })
    } finally {
      setLoading(false)
    }
  }

  async function handleLogin() {
    setError('')
    try {
      const data = await getBrokerLoginUrl()
      if (data.auth_url) {
        window.open(data.auth_url, 'tradejini_login', 'width=600,height=700')
        setStep('waiting')
        setTimeout(() => inputRef.current?.focus(), 300)
      } else {
        setError(data.error || 'Failed')
      }
    } catch (err) {
      setError(err.message)
    }
  }

  // Extract auth_code from any pasted URL or raw code
  function extractAuthCode(input) {
    const trimmed = input.trim()
    // Try to extract from URL like ...?auth_code=XXXXX&...
    const match = trimmed.match(/auth_code=([^&]+)/)
    if (match) return match[1]
    // If they pasted just the code itself
    if (trimmed.length > 10 && !trimmed.includes(' ')) return trimmed
    return null
  }

  async function handlePaste() {
    const code = extractAuthCode(pastedUrl)
    if (!code) {
      setError('Could not find auth code. Copy the full URL from the login window.')
      return
    }
    setStep('verifying')
    setError('')
    try {
      const result = await brokerVerifyAuthCode(code)
      if (result.status === 'ok') {
        setPastedUrl('')
        await checkStatus()
      } else {
        setError(result.error || 'Verification failed. Try logging in again.')
        setStep('waiting')
      }
    } catch (err) {
      setError(err.message)
      setStep('waiting')
    }
  }

  // Auto-submit when user pastes
  function handleInputChange(e) {
    const val = e.target.value
    setPastedUrl(val)
    if (val.includes('auth_code=')) {
      // Auto-submit after brief delay
      setTimeout(() => {
        const code = extractAuthCode(val)
        if (code) {
          setPastedUrl(val)
          handlePasteAuto(code)
        }
      }, 200)
    }
  }

  async function handlePasteAuto(code) {
    setStep('verifying')
    setError('')
    try {
      const result = await brokerVerifyAuthCode(code)
      if (result.status === 'ok') {
        setPastedUrl('')
        await checkStatus()
      } else {
        setError(result.error || 'Verification failed')
        setStep('waiting')
      }
    } catch (err) {
      setError(err.message)
      setStep('waiting')
    }
  }

  async function handleLogout() {
    await brokerLogout()
    setBrokerStatus({ connected: false, configured: true })
    setFunds(null)
    setStep('idle')
    setPastedUrl('')
  }

  const availableMargin = (() => {
    if (!funds?.fund_limit) return null
    const total = funds.fund_limit.find(f => f.title === 'Total Balance')
    const available = funds.fund_limit.find(f => f.title === 'Available Balance')
    return {
      total: total?.equityAmount || 0,
      available: available?.equityAmount || 0,
      used: (total?.equityAmount || 0) - (available?.equityAmount || 0),
    }
  })()

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 pointer-events-none" />
      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {brokerStatus?.connected
              ? <Link2 size={16} className="text-green-400" />
              : <Link2Off size={16} className="text-gray-500" />}
            <h3 className="text-sm font-semibold text-white">TradeJini Account</h3>
          </div>
          <button onClick={checkStatus} disabled={loading} className="text-gray-500 hover:text-gray-300 transition-colors">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
            <p className="text-[10px] text-red-400">{error}</p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-4">
            <Loader2 size={18} className="text-emerald-400 animate-spin" />
            <span className="text-xs text-gray-400 ml-2">Connecting...</span>
          </div>
        )}

        {/* Not configured */}
        {!loading && !brokerStatus?.configured && (
          <div className="text-xs text-gray-400 leading-relaxed">
            <p>Add <code className="text-emerald-400">TRADEJINI_API_KEY</code> & <code className="text-emerald-400">TRADEJINI_SECRET</code> to <code className="text-gray-300">backend/.env</code></p>
          </div>
        )}

        {/* Login flow */}
        {!loading && brokerStatus?.configured && !brokerStatus?.connected && (
          <div>
            {step === 'idle' && (
              <>
                <p className="text-xs text-gray-400 mb-3">Connect your TradeJini account to place trades.</p>
                <button
                  onClick={handleLogin}
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-xl py-2.5 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
                >
                  <ExternalLink size={14} />
                  Login with TradeJini
                </button>
              </>
            )}

            {step === 'waiting' && (
              <>
                <div className="bg-dark-600 rounded-xl p-3 mb-3">
                  <p className="text-xs text-gray-300 font-medium mb-1">After logging in:</p>
                  <p className="text-[11px] text-gray-400">Copy the full URL from the login window and paste it below</p>
                </div>
                <div className="relative">
                  <input
                    ref={inputRef}
                    type="text"
                    value={pastedUrl}
                    onChange={handleInputChange}
                    placeholder="Paste the URL here..."
                    className="w-full bg-dark-800 border border-dark-500 rounded-xl pl-3 pr-16 py-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                  />
                  <button
                    onClick={handlePaste}
                    disabled={!pastedUrl.trim()}
                    className="absolute right-1.5 top-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg text-[10px] font-semibold flex items-center gap-1 hover:opacity-90 disabled:opacity-30"
                  >
                    <ClipboardPaste size={10} /> Connect
                  </button>
                </div>
                <button onClick={() => { setStep('idle'); setError(''); setPastedUrl('') }} className="text-[10px] text-gray-500 mt-2 hover:text-gray-300">
                  Cancel
                </button>
              </>
            )}

            {step === 'verifying' && (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={18} className="text-green-400 animate-spin" />
                <span className="text-xs text-gray-300 ml-2">Verifying...</span>
              </div>
            )}
          </div>
        )}

        {/* Connected */}
        {!loading && brokerStatus?.connected && (
          <div>
            <div className="flex items-center gap-3 mb-3 bg-dark-600 rounded-xl p-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
                <User size={16} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{brokerStatus.profile?.name || 'Trader'}</p>
                <p className="text-[10px] text-gray-400">{brokerStatus.profile?.fy_id || ''}</p>
              </div>
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            </div>

            {availableMargin && (
              <div className="space-y-2 mb-3">
                <FundRow label="Available" value={availableMargin.available} color="text-green-400" />
                <FundRow label="Used" value={availableMargin.used} color="text-emerald-400" />
                <FundRow label="Total" value={availableMargin.total} color="text-white" />
              </div>
            )}

            <button
              onClick={handleLogout}
              className="w-full bg-dark-600 border border-dark-500 text-gray-400 rounded-xl py-2 text-xs font-medium flex items-center justify-center gap-2 hover:text-red-400 hover:border-red-500/30 transition-colors"
            >
              <LogOut size={12} /> Disconnect
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function FundRow({ label, value, color }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-gray-400">{label}</span>
      <span className={`text-xs font-semibold ${color}`}>
        {'\u20B9'}{Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
      </span>
    </div>
  )
}
