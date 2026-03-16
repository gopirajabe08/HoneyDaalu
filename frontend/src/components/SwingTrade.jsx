import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Loader2, AlertTriangle, Activity, Clock, Zap,
  ShieldAlert, Check, Repeat, TrendingUp, TrendingDown, Target, RefreshCw
} from 'lucide-react'
import { strategies } from '../data/mockData'
import {
  startSwingTrading, stopSwingTrading, getSwingStatus,
  startSwingPaperTrading, stopSwingPaperTrading, getSwingPaperStatus,
} from '../services/api'
import CapitalInput from './CapitalInput'
import DailyStrategyStats from './DailyStrategyStats'
import { LOG_COLORS } from '../utils/constants'
import { formatINR } from '../utils/formatters'

// Auto-determine scan interval from selected timeframes:
// All 1d → daily scheduled (9:20 AM + 3:35 PM), any 1h → every 2 hours
function getAutoScanInterval(selected) {
  const timeframes = Object.values(selected)
  if (timeframes.length === 0) return 0
  const hasHourly = timeframes.some(tf => tf === '1h')
  return hasHourly ? 120 : 0  // 120min=2h for hourly, 0=daily for daily
}

function getAutoScanLabel(selected) {
  const timeframes = Object.values(selected)
  if (timeframes.length === 0) return ''
  const hasHourly = timeframes.some(tf => tf === '1h')
  return hasHourly ? 'Every 2 hours (auto)' : 'Daily \u2014 9:20 AM + 3:35 PM (auto)'
}

// Only strategies with swingTimeframes
const swingStrategies = strategies.filter(s => s.swingTimeframes && s.swingTimeframes.length > 0)

export default function SwingTrade({ mode = 'live', capital, setCapital }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const [countdown, setCountdown] = useState(null)
  const [selected, setSelected] = useState({})
  const [refreshing, setRefreshing] = useState(false)
  const scanInterval = getAutoScanInterval(selected)
  const pollRef = useRef(null)
  const countdownRef = useRef(null)
  const logEndRef = useRef(null)

  const running = status?.is_running ?? false
  const selectedCount = Object.keys(selected).length
  const isLive = mode === 'live'

  const accentText = isLive ? 'text-emerald-400' : 'text-teal-400'
  const accentDot = isLive ? 'bg-emerald-400' : 'bg-teal-400'
  const accentBorder = isLive ? 'border-emerald-500/20' : 'border-teal-500/20'
  const accentBg = isLive ? 'from-emerald-500/5 to-green-500/5' : 'from-teal-500/5 to-cyan-500/5'
  const accentGrad = isLive ? 'from-emerald-500 to-green-500' : 'from-teal-500 to-cyan-500'
  const accentCheck = isLive ? 'bg-emerald-500 border-emerald-500' : 'bg-teal-500 border-teal-500'
  const accentSelected = isLive ? 'border-emerald-500/30' : 'border-teal-500/30'
  const accentTfActive = isLive
    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
    : 'bg-teal-500/20 text-teal-400 border border-teal-500/30'

  const pollStatus = useCallback(async () => {
    try {
      const data = isLive ? await getSwingStatus() : await getSwingPaperStatus()
      setStatus(data)
      if (data.next_scan_at) {
        const diff = Math.max(0, Math.floor((new Date(data.next_scan_at) - Date.now()) / 1000))
        setCountdown(diff)
      }
    } catch {}
  }, [isLive])

  useEffect(() => { pollStatus() }, [pollStatus])

  useEffect(() => {
    if (running) {
      pollRef.current = setInterval(pollStatus, 10000) // 10s — near real-time
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
            // For daily mode (interval=0), let pollStatus recalculate from next_scan_at
            const intervalMin = status?.scan_interval_minutes ?? 240
            return intervalMin > 0 ? intervalMin * 60 : 60
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
    const el = logEndRef.current
    if (el) {
      const container = el.closest('.overflow-y-auto')
      if (container) container.scrollTop = container.scrollHeight
    }
  }, [status?.logs?.length])

  function toggleStrategy(id) {
    setSelected(prev => {
      const next = { ...prev }
      if (next[id]) {
        delete next[id]
      } else {
        const strat = swingStrategies.find(s => s.id === id)
        next[id] = strat?.swingTimeframes?.[0] || '1d'
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
      const startFn = isLive ? startSwingTrading : startSwingPaperTrading
      const data = await startFn(stratList, capital, scanInterval)
      if (data.error) {
        setError(data.error)
      } else {
        // For daily mode, pollStatus will set countdown from next_scan_at
        if (scanInterval > 0) setCountdown(scanInterval * 60)
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
      const stopFn = isLive ? stopSwingTrading : stopSwingPaperTrading
      await stopFn()
      setCountdown(null)
      await pollStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function formatCountdown(sec) {
    if (sec == null) return '--:--:--'
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const logs = status?.logs ?? []
  const activeTrades = status?.active_trades ?? []
  const tradeHistory = status?.trade_history ?? []
  const runningStrategies = status?.strategies ?? []
  const totalPnl = status?.total_pnl ?? 0

  const allClosed = tradeHistory
  const winners = allClosed.filter(t => (t.pnl ?? 0) > 0)
  const losers = allClosed.filter(t => (t.pnl ?? 0) < 0)
  const winRate = allClosed.length > 0 ? Math.round((winners.length / allClosed.length) * 100) : 0

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Repeat size={18} className={accentText} />
        <p className="text-gray-400 text-xs">
          {isLive ? 'Live swing trading with CNC orders via Fyers' : 'Virtual swing trading with no real money'}
        </p>
        {running && <div className={`w-2.5 h-2.5 rounded-full ${accentDot} animate-pulse`} />}
        <button onClick={async () => { setRefreshing(true); await pollStatus(); setRefreshing(false) }} disabled={refreshing}
          className="ml-auto flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 bg-dark-700 border border-dark-500 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40">
          <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* ── Left: Trades + Stats ── */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Stats row */}
          {(running || allClosed.length > 0 || activeTrades.length > 0) && (
            <div className="grid grid-cols-6 gap-3">
              <StatCard label="Capital" value={status?.capital > 0 ? `₹${(status.capital >= 100000 ? (status.capital/100000).toFixed(1)+'L' : (status.capital/1000).toFixed(0)+'K')}` : '--'} color="text-white" />
              <StatCard label={isLive ? 'P&L' : 'Virtual P&L'} value={`${totalPnl >= 0 ? '+' : '-'}${formatINR(totalPnl)}`}
                color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
              <StatCard label="Win Rate" value={allClosed.length > 0 ? `${winRate}%` : '--'}
                sub={allClosed.length > 0 ? `${winners.length}W / ${losers.length}L` : ''} />
              <StatCard label="Scans" value={status?.scan_count ?? 0} />
              <StatCard label="Orders" value={status?.order_count ?? 0} />
              <StatCard label="Position" value={activeTrades.length > 0 ? '1 OPEN' : 'NONE'}
                color={activeTrades.length > 0 ? accentText : 'text-gray-500'} />
            </div>
          )}

          {/* Active swing position */}
          {activeTrades.length > 0 && (
            <div className={`bg-dark-700 rounded-2xl border ${accentBorder} p-5`}>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className={accentText} />
                Open {isLive ? '' : 'Virtual '}Swing Position
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Symbol', 'Signal', 'Strategy', 'Entry', 'SL', 'Target', 'LTP', 'Qty', 'Days', 'P&L'].map(h => (
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
                          <td className="px-3 py-2.5 text-xs text-gray-300">{formatINR(t.entry_price)}</td>
                          <td className="px-3 py-2.5 text-xs text-red-400">{formatINR(t.stop_loss)}</td>
                          <td className="px-3 py-2.5 text-xs text-green-400">{formatINR(t.target)}</td>
                          <td className="px-3 py-2.5 text-xs text-white font-medium">{formatINR(t.ltp || t.entry_price)}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{t.quantity}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{t.days_held ?? 0}d</td>
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
                Completed Swing Trades
                <span className="text-[10px] text-gray-500 font-normal">{tradeHistory.length} trades</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Symbol', 'Signal', 'Strategy', 'Entry', 'Exit', 'Qty', 'Days', 'P&L', 'Result'].map(h => (
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
                        reason === 'SL_HIT' ? 'SL HIT' : 'CLOSED'

                      return (
                        <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                          <td className="px-3 py-2.5 text-sm font-medium text-white">{t.symbol}</td>
                          <td className="px-3 py-2.5">
                            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                              {isBuy ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-[11px] text-gray-400">{stratName}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{formatINR(t.entry_price)}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{formatINR(t.exit_price || t.ltp)}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{t.quantity}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{t.days_held ?? 0}d</td>
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
              <Repeat size={36} className="text-gray-600 mx-auto mb-3" />
              <h3 className="text-white font-semibold mb-1">Swing Trading</h3>
              <p className="text-gray-500 text-xs max-w-md mx-auto">
                {isLive
                  ? 'Select strategies and click Start to begin live swing trading with CNC orders via Fyers.'
                  : 'Select strategies and click Start to begin virtual swing trading. Same rules as live \u2014 no money at risk.'}
              </p>
            </div>
          )}
        </div>

        {/* ── Right Sidebar: Controls + Log ── */}
        <div className="w-[300px] flex-shrink-0 space-y-4">
          <CapitalInput capital={capital} setCapital={setCapital} />

          {/* Control Panel */}
          <div className={`bg-dark-700 rounded-2xl border ${accentBorder} p-5 relative overflow-hidden`}>
            <div className={`absolute inset-0 bg-gradient-to-br ${accentBg} pointer-events-none`} />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-3">
                <Zap size={16} className={running ? accentText : 'text-gray-500'} />
                <h3 className="text-sm font-semibold text-white">
                  {isLive ? 'Live Engine' : 'Paper Engine'}
                </h3>
                {running && <div className={`w-2 h-2 rounded-full ${accentDot} animate-pulse ml-auto`} />}
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
                    <Badge color={isLive ? 'green' : 'teal'} text={isLive ? 'Live Swing' : 'Paper Swing'} />
                    <Badge color="gray" text={`Capital: \u20B9${(status?.capital ?? 0).toLocaleString('en-IN')}`} />
                    <Badge color={activeTrades.length > 0 ? 'yellow' : 'gray'} text={`${activeTrades.length} / ${isLive ? '1' : '5'} Positions`} />
                  </div>

                  <div className="grid grid-cols-3 gap-2 mb-3">
                    <MiniStat label="Scans" value={status?.scan_count ?? 0} />
                    <MiniStat label="Orders" value={status?.order_count ?? 0} />
                    <MiniStat label="P&L"
                      value={`${totalPnl >= 0 ? '+' : ''}\u20B9${Math.abs(totalPnl).toFixed(0)}`}
                      color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
                  </div>

                  <div className="flex items-center justify-between bg-dark-600 rounded-xl px-3 py-2 mb-3">
                    <div className="flex items-center gap-2">
                      <Clock size={12} className="text-gray-400" />
                      <span className="text-[10px] text-gray-400">Next scan in</span>
                    </div>
                    <span className={`text-xs font-semibold ${accentText} tabular-nums`}>{formatCountdown(countdown)}</span>
                  </div>

                  <button onClick={handleStop} disabled={loading}
                    className="w-full bg-dark-600 border border-dark-500 text-gray-300 rounded-xl py-2.5 text-xs font-semibold flex items-center justify-center gap-2 hover:text-white hover:border-dark-400 transition-all disabled:opacity-40 mb-2">
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <Square size={12} />}
                    Stop {isLive ? 'Live' : 'Paper'} Swing
                  </button>

                  {isLive && (
                    <button onClick={handleStop} disabled={loading}
                      className="w-full bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl py-2 text-[10px] font-semibold flex items-center justify-center gap-2 hover:bg-red-500/20 transition-all disabled:opacity-40">
                      <ShieldAlert size={12} />
                      Emergency Stop
                    </button>
                  )}
                </>
              ) : (
                <>
                  {/* Auto scan schedule */}
                  {selectedCount > 0 && (
                    <div className="mb-3 bg-dark-600 rounded-xl px-3 py-2">
                      <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-1">Scan Schedule</h4>
                      <p className={`text-[11px] ${accentText} font-medium`}>{getAutoScanLabel(selected)}</p>
                    </div>
                  )}

                  {/* Strategy selection */}
                  <div className="mb-3">
                    <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-2">Select Strategies (Swing-eligible)</h4>
                    <div className="space-y-1.5">
                      {swingStrategies.map(strat => {
                        const isSelected = !!selected[strat.id]
                        return (
                          <div key={strat.id} className={`rounded-xl border transition-all ${
                            isSelected ? `bg-dark-600 ${accentSelected}` : 'bg-dark-800 border-dark-600 hover:border-dark-500'
                          }`}>
                            <button onClick={() => toggleStrategy(strat.id)} className="w-full flex items-center gap-2.5 px-3 py-2">
                              <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border transition-all ${
                                isSelected ? accentCheck : 'border-gray-600 bg-dark-700'
                              }`}>
                                {isSelected && <Check size={10} className="text-white" />}
                              </div>
                              <div className="flex-1 text-left">
                                <span className="text-[11px] font-medium text-white">{strat.shortName}: {strat.name}</span>
                              </div>
                            </button>

                            {isSelected && (
                              <div className="flex gap-1 px-3 pb-2 pl-9">
                                {strat.swingTimeframes.map(tf => (
                                  <button key={tf} onClick={() => setTimeframe(strat.id, tf)}
                                    className={`px-2 py-0.5 rounded text-[9px] font-medium transition-all ${
                                      selected[strat.id] === tf
                                        ? accentTfActive
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

                  <div className="relative group">
                    <button onClick={handleStart} disabled={loading || selectedCount === 0}
                      className={`w-full bg-gradient-to-r ${accentGrad} text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed`}>
                      {loading ? (
                        <><Loader2 size={16} className="animate-spin" /> Starting...</>
                      ) : (
                        <><Play size={16} /> Start {isLive ? 'Live' : 'Paper'} Swing ({selectedCount})</>
                      )}
                    </button>
                    <div className="absolute bottom-full left-0 right-0 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                      <div className="bg-dark-800 border border-dark-500 rounded-lg p-3 shadow-lg text-[10px] text-gray-400 leading-relaxed">
                        <p className="text-emerald-400 font-semibold mb-1">Equity Swing Manual</p>
                        <p>CNC delivery orders. Positions carry overnight. BUY only (no short selling).</p>
                        <p className="mt-1">Scan: 9:20 AM + retry every 30m | SL/Target orders re-placed daily | Max {isLive ? '1' : '5'} position{isLive ? '' : 's'}</p>
                        <p className="mt-1">Price: ₹100-₹1,500 | Nifty filter: blocks BUY when Nifty {'<'} 50 SMA</p>
                      </div>
                    </div>
                  </div>

                  {isLive && (
                    <div className="mt-2 flex items-start gap-2 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
                      <ShieldAlert size={10} className="text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-[9px] text-red-400 leading-relaxed">
                        Live mode places real CNC orders on Fyers. Real money at risk.
                      </p>
                    </div>
                  )}
                </>
              )}

              <div className="mt-3 flex items-start gap-2 px-1">
                <AlertTriangle size={10} className="text-gray-600 flex-shrink-0 mt-0.5" />
                <p className="text-[9px] text-gray-600 leading-relaxed">
                  Swing mode &bull; Max 1 position &bull; 2% risk &bull; Positions carry overnight &bull; {isLive ? 'CNC orders via Fyers' : 'No real orders'}
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

      {/* Daily Strategy Performance */}
      <DailyStrategyStats source={isLive ? 'swing' : 'swing_paper'} days={14} accent={isLive ? 'emerald' : 'violet'} />
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
    teal: 'bg-teal-500/10 text-teal-400',
    green: 'bg-green-500/10 text-green-400',
    gray: 'bg-gray-500/10 text-gray-400',
    yellow: 'bg-yellow-500/10 text-yellow-400',
    red: 'bg-red-500/10 text-red-400',
  }
  return (
    <span className={`text-[9px] font-medium px-2 py-0.5 rounded-full ${colors[color]}`}>
      {text}
    </span>
  )
}
