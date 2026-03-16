import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Loader2, AlertTriangle, Activity, Clock, Zap,
  ShieldAlert, Check, BookOpen, TrendingUp, TrendingDown, Target
} from 'lucide-react'
import { strategies } from '../data/mockData'
import { startPaperTrading, stopPaperTrading, getPaperStatus } from '../services/api'
import CapitalInput from './CapitalInput'
import { LOG_COLORS } from '../utils/constants'
import { formatINR } from '../utils/formatters'

const POLL_INTERVAL = 15 * 60 * 1000
const SCAN_INTERVAL_MIN = 15

export default function PaperTrade({ capital, setCapital }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const [countdown, setCountdown] = useState(null)
  const pollRef = useRef(null)
  const countdownRef = useRef(null)
  const logEndRef = useRef(null)

  const [selected, setSelected] = useState({})

  const running = status?.is_running ?? false
  const selectedCount = Object.keys(selected).length

  const pollStatus = useCallback(async () => {
    try {
      const data = await getPaperStatus()
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
      const data = await startPaperTrading(stratList, capital)
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
      await stopPaperTrading()
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
  const tradeHistory = status?.trade_history ?? []
  const orderCutoff = status?.order_cutoff_passed ?? false
  const squaredOff = status?.squared_off ?? false
  const runningStrategies = status?.strategies ?? []
  const totalPnl = status?.total_pnl ?? 0

  // Combined stats
  const allClosed = tradeHistory
  const winners = allClosed.filter(t => (t.pnl ?? 0) > 0)
  const losers = allClosed.filter(t => (t.pnl ?? 0) < 0)
  const winRate = allClosed.length > 0 ? Math.round((winners.length / allClosed.length) * 100) : 0

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BookOpen size={22} className="text-blue-400" />
        <div>
          <h2 className="text-lg font-semibold text-white">Paper Trading</h2>
          <p className="text-gray-500 text-xs">Virtual auto-trading with no real money · Same rules as auto-trader</p>
        </div>
        {running && <div className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse ml-auto" />}
      </div>

      <div className="flex gap-6">
        {/* ── Left: Trades + Stats ── */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Stats row */}
          {(running || allClosed.length > 0 || activeTrades.length > 0) && (
            <div className="grid grid-cols-5 gap-3">
              <StatCard label="Virtual P&L" value={`${totalPnl >= 0 ? '+' : '-'}${formatINR(totalPnl)}`}
                color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
              <StatCard label="Win Rate" value={allClosed.length > 0 ? `${winRate}%` : '--'}
                sub={allClosed.length > 0 ? `${winners.length}W / ${losers.length}L` : ''} />
              <StatCard label="Scans" value={status?.scan_count ?? 0} />
              <StatCard label="Orders" value={status?.order_count ?? 0} />
              <StatCard label="Open" value={activeTrades.length} color="text-blue-400" />
            </div>
          )}

          {/* Active virtual trades */}
          {activeTrades.length > 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className="text-blue-400" />
                Open Virtual Positions
                <span className="text-[10px] text-gray-500 font-normal">LTP updates every scan</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Symbol', 'Signal', 'Strategy', 'Entry', 'SL', 'Target', 'LTP', 'Qty', 'P&L'].map(h => (
                        <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {activeTrades.map((t, i) => {
                      const isBuy = t.signal_type === 'BUY' || t.side === 1
                      const pnl = t.pnl ?? 0
                      const stratName = strategies.find(s => s.id === t.strategy)?.shortName || t.strategy
                      return (
                        <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                          <td className="px-3 py-2.5 text-sm font-medium text-white">{t.symbol}</td>
                          <td className="px-3 py-2.5">
                            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                              {isBuy ? <TrendingUp size={9} /> : <TrendingDown size={9} />}
                              {isBuy ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-[11px] text-gray-400">{stratName}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">₹{t.entry_price}</td>
                          <td className="px-3 py-2.5 text-xs text-red-400">₹{t.stop_loss}</td>
                          <td className="px-3 py-2.5 text-xs text-green-400">₹{t.target}</td>
                          <td className="px-3 py-2.5 text-xs text-white font-medium">₹{t.ltp || t.entry_price}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{t.quantity}</td>
                          <td className="px-3 py-2.5">
                            <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pnl >= 0 ? '+' : '-'}{formatINR(pnl)}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Trade History */}
          {tradeHistory.length > 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Clock size={16} className="text-gray-400" />
                Completed Trades
                <span className="text-[10px] text-gray-500 font-normal">{tradeHistory.length} trades</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Symbol', 'Signal', 'Strategy', 'Entry', 'Exit', 'Qty', 'P&L', 'Result'].map(h => (
                        <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...tradeHistory].reverse().map((t, i) => {
                      const isBuy = t.signal_type === 'BUY' || t.side === 1
                      const pnl = t.pnl ?? 0
                      const stratName = strategies.find(s => s.id === t.strategy)?.shortName || t.strategy
                      const reason = t.exit_reason || ''
                      const resultColor = reason === 'TARGET_HIT' ? 'bg-green-500/15 text-green-400' :
                        reason === 'SL_HIT' ? 'bg-red-500/15 text-red-400' : 'bg-gray-500/15 text-gray-400'
                      const resultLabel = reason === 'TARGET_HIT' ? 'TARGET' :
                        reason === 'SL_HIT' ? 'SL HIT' : reason === 'SQUARE_OFF' ? 'SQ OFF' : 'CLOSED'

                      return (
                        <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                          <td className="px-3 py-2.5 text-sm font-medium text-white">{t.symbol}</td>
                          <td className="px-3 py-2.5">
                            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                              {isBuy ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-[11px] text-gray-400">{stratName}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">₹{t.entry_price}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">₹{t.exit_price || t.ltp || '--'}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{t.quantity}</td>
                          <td className="px-3 py-2.5">
                            <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pnl >= 0 ? '+' : '-'}{formatINR(pnl)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${resultColor}`}>{resultLabel}</span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!running && activeTrades.length === 0 && tradeHistory.length === 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-12 text-center">
              <BookOpen size={36} className="text-gray-600 mx-auto mb-3" />
              <h3 className="text-white font-semibold mb-1">Paper Trading</h3>
              <p className="text-gray-500 text-xs max-w-md mx-auto">
                Select strategies and click Start to begin virtual auto-trading.
                Same scanning and rules as the real auto-trader — no money at risk.
              </p>
            </div>
          )}
        </div>

        {/* ── Right Sidebar: Controls + Log ── */}
        <div className="w-[300px] flex-shrink-0 space-y-4">
          <CapitalInput capital={capital} setCapital={setCapital} />
          {/* Control Panel */}
          <div className="bg-dark-700 rounded-2xl border border-blue-500/20 p-5 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 pointer-events-none" />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-3">
                <Zap size={16} className={running ? 'text-blue-400' : 'text-gray-500'} />
                <h3 className="text-sm font-semibold text-white">Paper Engine</h3>
                {running && <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse ml-auto" />}
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
                  <p className="text-[10px] text-red-400">{error}</p>
                </div>
              )}

              {running ? (
                <>
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

                  <div className="flex gap-2 mb-3 flex-wrap">
                    <Badge color="blue" text="Virtual Mode" />
                    {orderCutoff && <Badge color="yellow" text="No new orders (past 2 PM)" />}
                    {squaredOff && <Badge color="purple" text="Squared off" />}
                  </div>

                  <div className="grid grid-cols-3 gap-2 mb-3">
                    <MiniStat label="Scans" value={status?.scan_count ?? 0} />
                    <MiniStat label="Orders" value={status?.order_count ?? 0} />
                    <MiniStat label="P&L"
                      value={`${totalPnl >= 0 ? '+' : ''}₹${Math.abs(totalPnl).toFixed(0)}`}
                      color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
                  </div>

                  {!orderCutoff && (
                    <div className="flex items-center justify-between bg-dark-600 rounded-xl px-3 py-2 mb-3">
                      <div className="flex items-center gap-2">
                        <Clock size={12} className="text-gray-400" />
                        <span className="text-[10px] text-gray-400">Next scan in</span>
                      </div>
                      <span className="text-xs font-semibold text-blue-400 tabular-nums">{formatCountdown(countdown)}</span>
                    </div>
                  )}

                  <button onClick={handleStop} disabled={loading}
                    className="w-full bg-dark-600 border border-dark-500 text-gray-300 rounded-xl py-2.5 text-xs font-semibold flex items-center justify-center gap-2 hover:text-white hover:border-dark-400 transition-all disabled:opacity-40">
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <Square size={12} />}
                    Stop Paper Trading
                  </button>
                </>
              ) : (
                <>
                  <div className="mb-3">
                    <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-2">Select Strategies</h4>
                    <div className="space-y-1.5">
                      {strategies.map(strat => {
                        const isSelected = !!selected[strat.id]
                        return (
                          <div key={strat.id} className={`rounded-xl border transition-all ${
                            isSelected ? 'bg-dark-600 border-blue-500/30' : 'bg-dark-800 border-dark-600 hover:border-dark-500'
                          }`}>
                            <button onClick={() => toggleStrategy(strat.id)} className="w-full flex items-center gap-2.5 px-3 py-2">
                              <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border transition-all ${
                                isSelected ? 'bg-blue-500 border-blue-500' : 'border-gray-600 bg-dark-700'
                              }`}>
                                {isSelected && <Check size={10} className="text-white" />}
                              </div>
                              <div className="flex-1 text-left">
                                <span className="text-[11px] font-medium text-white">{strat.shortName}: {strat.name}</span>
                              </div>
                            </button>

                            {isSelected && (
                              <div className="flex gap-1 px-3 pb-2 pl-9">
                                {strat.timeframes.map(tf => (
                                  <button key={tf} onClick={() => setTimeframe(strat.id, tf)}
                                    className={`px-2 py-0.5 rounded text-[9px] font-medium transition-all ${
                                      selected[strat.id] === tf
                                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                        : 'bg-dark-700 text-gray-500 border border-dark-500 hover:text-gray-300'
                                    }`}>
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

                  <button onClick={handleStart} disabled={loading || selectedCount === 0}
                    className="w-full bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed">
                    {loading ? (
                      <><Loader2 size={16} className="animate-spin" /> Starting...</>
                    ) : (
                      <><Play size={16} /> Start Paper Trading ({selectedCount})</>
                    )}
                  </button>
                </>
              )}

              <div className="mt-3 flex items-start gap-2 px-1">
                <AlertTriangle size={10} className="text-gray-600 flex-shrink-0 mt-0.5" />
                <p className="text-[9px] text-gray-600 leading-relaxed">
                  Virtual mode &bull; Max 3 positions &bull; 2% risk &bull; 15 min scan &bull; No real orders placed
                </p>
              </div>
            </div>
          </div>

          {/* Live Log */}
          <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
            <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-2">
              {running ? 'Live Log' : logs.length > 0 ? 'Last Session Log' : 'Log'}
            </h4>
            <div className="bg-dark-800 rounded-xl border border-dark-600 p-2 max-h-72 overflow-y-auto font-mono">
              {logs.length === 0 ? (
                <p className="text-[10px] text-gray-600 text-center py-4">No activity yet</p>
              ) : (
                (running ? logs : logs.slice(-15)).map((entry, i) => (
                  <div key={i} className="flex gap-2 text-[10px] leading-relaxed py-0.5">
                    <span className="text-gray-600 flex-shrink-0 tabular-nums">{entry.timestamp}</span>
                    <span className={`flex-shrink-0 font-semibold w-16 ${LOG_COLORS[entry.level] || 'text-gray-400'}`}>
                      {entry.level}
                    </span>
                    <span className="text-gray-300 break-words">{entry.message}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color = 'text-white', sub }) {
  return (
    <div className="bg-dark-700 border border-dark-500 rounded-xl p-3">
      <div className="text-gray-500 text-[10px] uppercase">{label}</div>
      <div className={`text-base font-bold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-500">{sub}</div>}
    </div>
  )
}

function MiniStat({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-dark-600 rounded-lg px-2 py-2 text-center">
      <p className={`text-xs font-semibold tabular-nums ${color}`}>{value}</p>
      <p className="text-[9px] text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

function Badge({ color, text }) {
  const colors = {
    blue: 'bg-blue-500/10 text-blue-400',
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
