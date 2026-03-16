import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Square, Loader2, AlertTriangle, Activity, Clock, Zap, ShieldAlert, Check } from 'lucide-react'
import { strategies } from '../data/mockData'
import { startAutoTrading, stopAutoTrading, getAutoStatus } from '../services/api'
import { LOG_COLORS } from '../utils/constants'

const POLL_INTERVAL = 15 * 60 * 1000
const SCAN_INTERVAL_MIN = 15

export default function AutoTrader({ capital }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const [countdown, setCountdown] = useState(null)
  const pollRef = useRef(null)
  const countdownRef = useRef(null)
  const logEndRef = useRef(null)

  // Multi-strategy selection: { strategyId: timeframe }
  const [selected, setSelected] = useState({})

  const running = status?.is_running ?? false
  const selectedCount = Object.keys(selected).length

  const pollStatus = useCallback(async () => {
    try {
      const data = await getAutoStatus()
      setStatus(data)
      if (data.next_scan_at) {
        const diff = Math.max(0, Math.floor((new Date(data.next_scan_at) - Date.now()) / 1000))
        setCountdown(diff)
      }
    } catch {}
  }, [])

  useEffect(() => { pollStatus() }, [pollStatus])

  useEffect(() => {
    if (running) {
      pollRef.current = setInterval(pollStatus, POLL_INTERVAL)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [running, pollStatus])

  useEffect(() => {
    if (running && countdown !== null && countdown > 0) {
      countdownRef.current = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            pollStatus()
            return SCAN_INTERVAL_MIN * 60
          }
          return prev - 1
        })
      }, 1000)
    } else {
      clearInterval(countdownRef.current)
    }
    return () => clearInterval(countdownRef.current)
  }, [running, countdown !== null])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [status?.logs?.length])

  function toggleStrategy(id) {
    setSelected(prev => {
      const next = { ...prev }
      if (next[id]) {
        delete next[id]
      } else {
        const strat = strategies.find(s => s.id === id)
        next[id] = strat?.timeframes?.[0] || '15m'
      }
      return next
    })
  }

  function setTimeframe(id, tf) {
    setSelected(prev => ({ ...prev, [id]: tf }))
  }

  async function handleStart() {
    if (selectedCount === 0) return
    setLoading(true)
    setError('')
    try {
      const stratList = Object.entries(selected).map(([strategy, timeframe]) => ({ strategy, timeframe }))
      const data = await startAutoTrading(stratList, capital)
      if (data.error) {
        setError(data.error)
      } else {
        setCountdown(SCAN_INTERVAL_MIN * 60)
        await pollStatus()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleStop() {
    setLoading(true)
    setError('')
    try {
      await stopAutoTrading()
      setCountdown(null)
      await pollStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function formatCountdown(sec) {
    if (sec == null) return '--:--'
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const logs = status?.logs ?? []
  const activeTrades = status?.active_trades ?? []
  const orderCutoff = status?.order_cutoff_passed ?? false
  const squaredOff = status?.squared_off ?? false
  const runningStrategies = status?.strategies ?? []

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-pink-500/5 pointer-events-none" />
      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <Zap size={16} className={running ? 'text-green-400' : 'text-orange-400'} />
          <h3 className="text-sm font-semibold text-white">Auto-Trading</h3>
          {running && <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse ml-auto" />}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
            <p className="text-[10px] text-red-400">{error}</p>
          </div>
        )}

        {running ? (
          <>
            {/* Running strategies */}
            <div className="bg-dark-600 rounded-xl px-3 py-2.5 mb-3">
              <p className="text-[10px] text-gray-400 mb-1.5">Running {runningStrategies.length} strateg{runningStrategies.length === 1 ? 'y' : 'ies'}</p>
              <div className="flex flex-wrap gap-1.5">
                {runningStrategies.map((s, i) => {
                  const strat = strategies.find(st => st.id === s.strategy)
                  return (
                    <span key={i} className="text-[9px] bg-dark-700 text-white px-2 py-0.5 rounded-md border border-dark-500">
                      {strat?.shortName || s.strategy} <span className="text-gray-500">{s.timeframe}</span>
                    </span>
                  )
                })}
              </div>
            </div>

            {/* Status badges */}
            <div className="flex gap-2 mb-3 flex-wrap">
              <Badge color="green" text="Active" />
              {orderCutoff && <Badge color="yellow" text="No new orders (past 2 PM)" />}
              {squaredOff && <Badge color="purple" text="Squared off" />}
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              <StatBox label="Scans" value={status?.scan_count ?? 0} />
              <StatBox label="Orders" value={status?.order_count ?? 0} />
              <StatBox
                label="P&L"
                value={`${(status?.total_pnl ?? 0) >= 0 ? '+' : ''}${'\u20B9'}${(status?.total_pnl ?? 0).toFixed(0)}`}
                color={(status?.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}
              />
            </div>

            {/* Next scan countdown */}
            {!orderCutoff && (
              <div className="flex items-center justify-between bg-dark-600 rounded-xl px-3 py-2 mb-3">
                <div className="flex items-center gap-2">
                  <Clock size={12} className="text-gray-400" />
                  <span className="text-[10px] text-gray-400">Next scan in</span>
                </div>
                <span className="text-xs font-semibold text-orange-400 tabular-nums">{formatCountdown(countdown)}</span>
              </div>
            )}

            {/* Active trades */}
            {activeTrades.length > 0 && (
              <div className="mb-3">
                <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-1.5">Open Trades</h4>
                <div className="space-y-1">
                  {activeTrades.map((trade, i) => (
                    <div key={i} className="flex items-center justify-between bg-dark-600 rounded-lg px-3 py-1.5">
                      <div>
                        <span className="text-[11px] font-medium text-white">{trade.symbol}</span>
                        <span className="text-[9px] text-gray-500 ml-1.5">@ {'\u20B9'}{trade.entry_price}</span>
                        {trade.strategy && (
                          <span className="text-[8px] text-gray-600 ml-1">[{trade.strategy}]</span>
                        )}
                      </div>
                      <span className={`text-[11px] font-semibold tabular-nums ${
                        (trade.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {(trade.pnl ?? 0) >= 0 ? '+' : ''}{'\u20B9'}{(trade.pnl ?? 0).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Live Log */}
            <div className="mb-3">
              <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-1.5">Live Log</h4>
              <div className="bg-dark-800 rounded-xl border border-dark-600 p-2 max-h-48 overflow-y-auto font-mono">
                {logs.length === 0 ? (
                  <p className="text-[10px] text-gray-600 text-center py-2">Waiting for activity...</p>
                ) : (
                  logs.map((entry, i) => (
                    <div key={i} className="flex gap-2 text-[10px] leading-relaxed py-0.5">
                      <span className="text-gray-600 flex-shrink-0 tabular-nums">{entry.timestamp}</span>
                      <span className={`flex-shrink-0 font-semibold w-14 ${LOG_COLORS[entry.level] || 'text-gray-400'}`}>
                        {entry.level}
                      </span>
                      <span className="text-gray-300 break-words">{entry.message}</span>
                    </div>
                  ))
                )}
                <div ref={logEndRef} />
              </div>
            </div>

            {/* Stop buttons */}
            <button
              onClick={handleStop}
              disabled={loading}
              className="w-full bg-dark-600 border border-dark-500 text-gray-300 rounded-xl py-2.5 text-xs font-semibold flex items-center justify-center gap-2 hover:text-white hover:border-dark-400 transition-all disabled:opacity-40 mb-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Square size={12} />}
              Stop Auto-Trading
            </button>

            <button
              onClick={handleStop}
              disabled={loading}
              className="w-full bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl py-2 text-[10px] font-semibold flex items-center justify-center gap-2 hover:bg-red-500/20 transition-all disabled:opacity-40"
            >
              <ShieldAlert size={12} />
              Emergency Stop
            </button>
          </>
        ) : (
          <>
            {/* Strategy selection */}
            <div className="mb-3">
              <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-2">Select Strategies</h4>
              <div className="space-y-1.5">
                {strategies.map(strat => {
                  const isSelected = !!selected[strat.id]
                  return (
                    <div key={strat.id} className={`rounded-xl border transition-all ${
                      isSelected
                        ? 'bg-dark-600 border-orange-500/30'
                        : 'bg-dark-800 border-dark-600 hover:border-dark-500'
                    }`}>
                      <button
                        onClick={() => toggleStrategy(strat.id)}
                        className="w-full flex items-center gap-2.5 px-3 py-2"
                      >
                        <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border transition-all ${
                          isSelected
                            ? 'bg-orange-500 border-orange-500'
                            : 'border-gray-600 bg-dark-700'
                        }`}>
                          {isSelected && <Check size={10} className="text-white" />}
                        </div>
                        <div className="flex-1 text-left">
                          <span className="text-[11px] font-medium text-white">{strat.shortName}: {strat.name}</span>
                        </div>
                      </button>

                      {/* Timeframe selector when selected */}
                      {isSelected && (
                        <div className="flex gap-1 px-3 pb-2 pl-9">
                          {strat.timeframes.map(tf => (
                            <button
                              key={tf}
                              onClick={() => setTimeframe(strat.id, tf)}
                              className={`px-2 py-0.5 rounded text-[9px] font-medium transition-all ${
                                selected[strat.id] === tf
                                  ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                                  : 'bg-dark-700 text-gray-500 border border-dark-500 hover:text-gray-300'
                              }`}
                            >
                              {tf}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Last session log */}
            {logs.length > 0 && (
              <div className="mb-3">
                <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-1.5">Last Session Log</h4>
                <div className="bg-dark-800 rounded-xl border border-dark-600 p-2 max-h-32 overflow-y-auto font-mono">
                  {logs.slice(-10).map((entry, i) => (
                    <div key={i} className="flex gap-2 text-[10px] leading-relaxed py-0.5">
                      <span className="text-gray-600 flex-shrink-0 tabular-nums">{entry.timestamp}</span>
                      <span className={`flex-shrink-0 font-semibold w-14 ${LOG_COLORS[entry.level] || 'text-gray-400'}`}>
                        {entry.level}
                      </span>
                      <span className="text-gray-300">{entry.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Start button */}
            <button
              onClick={handleStart}
              disabled={loading || selectedCount === 0}
              className="w-full bg-gradient-to-r from-orange-500 to-pink-500 text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? (
                <><Loader2 size={16} className="animate-spin" /> Starting...</>
              ) : (
                <><Play size={16} /> Start Auto-Trading ({selectedCount} strateg{selectedCount === 1 ? 'y' : 'ies'})</>
              )}
            </button>
          </>
        )}

        {/* Safety info */}
        <div className="mt-3 flex items-start gap-2 px-1">
          <AlertTriangle size={10} className="text-gray-600 flex-shrink-0 mt-0.5" />
          <p className="text-[9px] text-gray-600 leading-relaxed">
            Max 3 positions &bull; 2% risk &bull; 15 min scan &bull; Orders stop at 2:00 PM &bull; Square-off at 3:15 PM
          </p>
        </div>
      </div>

    </div>
  )
}

function Badge({ color, text }) {
  const colors = {
    green: 'bg-green-500/10 text-green-400',
    yellow: 'bg-yellow-500/10 text-yellow-400',
    purple: 'bg-purple-500/10 text-purple-400',
    red: 'bg-red-500/10 text-red-400',
  }
  return (
    <span className={`text-[9px] font-medium px-2 py-0.5 rounded-full ${colors[color]}`}>
      {text}
    </span>
  )
}

function StatBox({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-dark-600 rounded-lg px-2 py-2 text-center">
      <p className={`text-xs font-semibold tabular-nums ${color}`}>{value}</p>
      <p className="text-[9px] text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}
