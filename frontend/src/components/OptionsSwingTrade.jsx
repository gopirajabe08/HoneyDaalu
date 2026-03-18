import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Loader2, AlertTriangle, Activity, Clock, Zap,
  ShieldAlert, Check, TrendingUp, TrendingDown, Repeat, RefreshCw, Calendar
} from 'lucide-react'
import { optionsStrategies } from '../data/mockData'
import {
  startOptionsSwingTrading, stopOptionsSwingTrading, getOptionsSwingStatus,
  startOptionsSwingPaperTrading, stopOptionsSwingPaperTrading, getOptionsSwingPaperStatus,
  getMarketRegime,
} from '../services/api'
import CapitalInput from './CapitalInput'
import DailyStrategyStats from './DailyStrategyStats'
import { LOG_COLORS, CONVICTION_COLORS, CONVICTION_LABELS, UNDERLYING_OPTIONS } from '../utils/constants'
import { formatINR, formatLegs } from '../utils/formatters'

const POLL_INTERVAL = 10 * 1000  // 10s — near real-time
const REGIME_INTERVAL = 5 * 60 * 1000  // 5 min

function daysUntilExpiry(expiryDate) {
  if (!expiryDate) return null
  const now = new Date()
  const exp = new Date(expiryDate)
  const diff = Math.ceil((exp - now) / (1000 * 60 * 60 * 24))
  return Math.max(0, diff)
}

export default function OptionsSwingTrade({ mode, capital, setCapital }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const [regime, setRegime] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [selectedUnderlyings, setSelectedUnderlyings] = useState({ NIFTY: true, BANKNIFTY: true })
  const pollRef = useRef(null)
  const regimeRef = useRef(null)
  const logEndRef = useRef(null)

  const isLive = mode === 'live'
  const running = status?.is_running ?? false

  const accentText = isLive ? 'text-emerald-400' : 'text-teal-400'
  const accentDot = isLive ? 'bg-emerald-400' : 'bg-teal-400'
  const accentBorder = isLive ? 'border-emerald-500/20' : 'border-teal-500/20'
  const accentBg = isLive ? 'from-emerald-500/5 to-green-500/5' : 'from-teal-500/5 to-cyan-500/5'
  const accentGrad = isLive ? 'from-emerald-500 to-green-500' : 'from-teal-500 to-cyan-500'
  const accentCheck = isLive ? 'bg-emerald-500 border-emerald-500' : 'bg-teal-500 border-teal-500'

  const pollStatus = useCallback(async () => {
    try {
      const data = isLive ? await getOptionsSwingStatus() : await getOptionsSwingPaperStatus()
      setStatus(data)
    } catch {}
  }, [isLive])

  const fetchRegime = useCallback(async () => {
    try {
      const data = await getMarketRegime('NIFTY')
      setRegime(data)
    } catch {}
  }, [])

  // Poll status on mount
  useEffect(() => { pollStatus() }, [pollStatus])

  // Fetch regime on mount
  useEffect(() => { fetchRegime() }, [fetchRegime])

  // Poll status every 60s while running
  useEffect(() => {
    if (running) {
      pollRef.current = setInterval(pollStatus, POLL_INTERVAL)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [running, pollStatus])

  // Refresh regime every 5 min while running
  useEffect(() => {
    if (running) {
      regimeRef.current = setInterval(fetchRegime, REGIME_INTERVAL)
    } else {
      clearInterval(regimeRef.current)
    }
    return () => clearInterval(regimeRef.current)
  }, [running, fetchRegime])

  // Auto-scroll log
  useEffect(() => {
    const el = logEndRef.current
    if (el) {
      const container = el.closest('.overflow-y-auto')
      if (container) container.scrollTop = container.scrollHeight
    }
  }, [status?.logs?.length])

  function toggleUnderlying(sym) {
    setSelectedUnderlyings(prev => ({ ...prev, [sym]: !prev[sym] }))
  }

  const activeUnderlyings = UNDERLYING_OPTIONS.filter(u => selectedUnderlyings[u])

  async function handleStart() {
    if (activeUnderlyings.length === 0) return
    setLoading(true)
    setError('')
    try {
      const startFn = isLive ? startOptionsSwingTrading : startOptionsSwingPaperTrading
      const data = await startFn(capital, activeUnderlyings)
      if (data.error) {
        setError(data.error)
      } else {
        await pollStatus()
        await fetchRegime()
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
      const stopFn = isLive ? stopOptionsSwingTrading : stopOptionsSwingPaperTrading
      await stopFn()
      await pollStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const logs = status?.logs ?? []
  const activeTrades = status?.active_positions ?? []
  const tradeHistory = status?.trade_history ?? []
  const totalPnl = status?.total_pnl ?? 0

  const allClosed = tradeHistory
  const winners = allClosed.filter(t => (t.pnl ?? 0) > 0)
  const losers = allClosed.filter(t => (t.pnl ?? 0) < 0)
  const winRate = allClosed.length > 0 ? Math.round((winners.length / allClosed.length) * 100) : 0

  return (
    <div className="space-y-5">
      {/* Status bar */}
      <div className="flex items-center gap-3">
        {running && <div className={`w-2.5 h-2.5 rounded-full ${accentDot} animate-pulse`} />}
        {running && <span className={`text-xs font-medium ${accentText}`}>Running</span>}
        <button onClick={async () => { setRefreshing(true); await pollStatus(); await fetchRegime(); setRefreshing(false) }} disabled={refreshing}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 bg-dark-700 border border-dark-500 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40">
          <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* -- Left: Trades + Stats -- */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Market Regime Panel */}
          {regime && (
            <div className="bg-dark-700 rounded-2xl border border-violet-500/20 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className="text-violet-400" />
                Market Regime
                <span className="text-[9px] font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 ml-auto">
                  Monthly Expiry
                </span>
              </h3>
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-dark-600 rounded-xl px-3 py-2.5">
                  <p className="text-[10px] text-gray-500 uppercase mb-1">Conviction</p>
                  <span className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full ${CONVICTION_COLORS[regime.conviction] || 'bg-gray-500/15 text-gray-400'}`}>
                    {CONVICTION_LABELS[regime.conviction] || regime.conviction || '--'}
                  </span>
                </div>
                <div className="bg-dark-600 rounded-xl px-3 py-2.5">
                  <p className="text-[10px] text-gray-500 uppercase mb-1">VIX</p>
                  <p className="text-sm font-bold text-white">{regime.components?.vix ?? '--'}</p>
                  {regime.components?.vix_signal && <p className="text-[9px] text-gray-400">{regime.components.vix_signal}</p>}
                </div>
                <div className="bg-dark-600 rounded-xl px-3 py-2.5">
                  <p className="text-[10px] text-gray-500 uppercase mb-1">PCR</p>
                  <p className="text-sm font-bold text-white">{regime.components?.pcr ?? '--'}</p>
                  {regime.components?.pcr_signal && <p className="text-[9px] text-gray-400">{regime.components.pcr_signal}</p>}
                </div>
                <div className="bg-dark-600 rounded-xl px-3 py-2.5">
                  <p className="text-[10px] text-gray-500 uppercase mb-1">Recommended</p>
                  <p className="text-[11px] font-semibold text-violet-400">
                    {regime.recommended_strategies?.length > 0
                      ? regime.recommended_strategies.map(id => optionsStrategies.find(s => s.id === id)?.name || id).join(', ')
                      : '--'}
                  </p>
                </div>
              </div>
            </div>
          )}

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
              <StatCard label="Open" value={activeTrades.length} color={accentText} />
            </div>
          )}

          {/* Active trades — hidden for live */}
          {!isLive && activeTrades.length > 0 && (
            <div className={`bg-dark-700 rounded-2xl border ${accentBorder} p-5`}>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className={accentText} />
                Open {isLive ? '' : 'Virtual '}Swing Options Positions
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Underlying', 'Strategy', 'Legs', 'Net Premium', 'P&L', 'Max Risk', 'Days Held', 'Expiry'].map(h => (
                        <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {activeTrades.map((t, i) => {
                      const pnl = t.pnl ?? 0
                      const stratInfo = optionsStrategies.find(s => s.id === t.strategy)
                      const daysHeld = t.placed_at
                        ? Math.max(0, Math.ceil((Date.now() - new Date(t.placed_at)) / (1000 * 60 * 60 * 24)))
                        : 0
                      const expiryDays = daysUntilExpiry(t.expiry_date)
                      return (
                        <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                          <td className="px-3 py-2.5 text-sm font-medium text-white">{t.underlying}</td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-1.5">
                              <span className="text-[11px] font-medium text-white">{t.strategy_name || stratInfo?.name || t.strategy}</span>
                              {(stratInfo?.type || t.type) && (
                                <span className={`text-[8px] font-semibold px-1.5 py-0.5 rounded ${
                                  (stratInfo?.type || t.type) === 'credit' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-blue-500/15 text-blue-400'
                                }`}>
                                  {(stratInfo?.type || t.type).toUpperCase()}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-[10px] text-gray-300 font-mono">{formatLegs(t.legs)}</span>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{formatINR(t.net_premium)}</td>
                          <td className="px-3 py-2.5">
                            <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pnl >= 0 ? '+' : '-'}{formatINR(pnl)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-red-400">{formatINR(t.max_risk)}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{daysHeld}d</td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-1.5">
                              <Calendar size={10} className="text-gray-500" />
                              <span className="text-[10px] text-gray-300">{t.expiry || '--'}</span>
                              {expiryDays !== null && (
                                <span className={`text-[8px] font-semibold px-1.5 py-0.5 rounded ${
                                  expiryDays <= 3 ? 'bg-red-500/15 text-red-400' : expiryDays <= 7 ? 'bg-yellow-500/15 text-yellow-400' : 'bg-gray-500/15 text-gray-400'
                                }`}>
                                  {expiryDays}d left
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Trade History — hidden for live */}
          {!isLive && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Clock size={16} className="text-gray-400" />
                Completed Swing Trades
                <span className="text-[10px] text-gray-500 font-normal">{tradeHistory.length} trades</span>
              </h3>
              {tradeHistory.length === 0 ? (
                <p className="text-xs text-gray-600 text-center py-4">No completed swing options trades yet.</p>
              ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Underlying', 'Strategy', 'Legs', 'Net Premium', 'Days', 'P&L', 'Result'].map(h => (
                        <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...tradeHistory].reverse().map((t, i) => {
                      const pnl = t.pnl ?? 0
                      const stratInfo = optionsStrategies.find(s => s.id === t.strategy)
                      const reason = t.exit_reason || t.status || ''
                      const resultColor = reason === 'TARGET_HIT' || reason === 'PROFIT'
                        ? 'bg-green-500/15 text-green-400'
                        : reason === 'SL_HIT' || reason === 'LOSS'
                        ? 'bg-red-500/15 text-red-400'
                        : 'bg-gray-500/15 text-gray-400'
                      const resultLabel = reason === 'TARGET_HIT' || reason === 'PROFIT' ? 'PROFIT'
                        : reason === 'SL_HIT' || reason === 'LOSS' ? 'SL HIT'
                        : reason === 'EXPIRED' ? 'EXPIRED'
                        : 'CLOSED'

                      return (
                        <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                          <td className="px-3 py-2.5 text-sm font-medium text-white">{t.underlying}</td>
                          <td className="px-3 py-2.5 text-[11px] text-gray-400">{t.strategy_name || stratInfo?.name || t.strategy}</td>
                          <td className="px-3 py-2.5">
                            <span className="text-[10px] text-gray-300 font-mono">{formatLegs(t.legs)}</span>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{formatINR(t.net_premium)}</td>
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
              )}
            </div>
          )}

          {/* Daily Strategy Performance */}
          <DailyStrategyStats source={isLive ? 'options_swing' : 'options_swing_paper'} days={14} accent={isLive ? 'emerald' : 'teal'} />

          {/* Empty state */}
          {!running && activeTrades.length === 0 && tradeHistory.length === 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-12 text-center">
              <Repeat size={36} className="text-gray-600 mx-auto mb-3" />
              <h3 className="text-white font-semibold mb-1">Options Swing Trading</h3>
              <p className="text-gray-500 text-xs max-w-md mx-auto">
                {isLive
                  ? 'Select underlyings and click Start to begin live options swing trading. Uses monthly expiry for longer-dated positions.'
                  : 'Select underlyings and click Start to begin virtual options swing trading. Same rules as live -- no money at risk.'}
              </p>
            </div>
          )}
        </div>

        {/* -- Right Sidebar: Controls + Log -- */}
        <div className="w-[300px] flex-shrink-0 space-y-4">
          <CapitalInput capital={capital} setCapital={setCapital} />

          {/* Control Panel */}
          <div className={`bg-dark-700 rounded-2xl border ${accentBorder} p-5 relative overflow-hidden`}>
            <div className={`absolute inset-0 bg-gradient-to-br ${accentBg} pointer-events-none`} />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-3">
                <Zap size={16} className={running ? accentText : 'text-gray-500'} />
                <h3 className="text-sm font-semibold text-white">
                  {isLive ? 'Live Swing Engine' : 'Paper Swing Engine'}
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
                    <p className="text-[10px] text-gray-400 mb-1.5">Trading underlyings</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(status?.underlyings ?? []).map((u, i) => (
                        <span key={i} className="text-[9px] bg-dark-700 text-white px-2 py-0.5 rounded-md border border-dark-500">
                          {u}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2 mb-3 flex-wrap">
                    <Badge color={isLive ? 'green' : 'teal'} text={isLive ? 'Live Swing' : 'Paper Swing'} />
                    <Badge color="amber" text="Monthly Expiry" />
                    <Badge color="gray" text={`Capital: \u20B9${(status?.capital ?? 0).toLocaleString('en-IN')}`} />
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
                      <span className="text-[10px] text-gray-400">Strategy selection</span>
                    </div>
                    <span className={`text-[10px] font-semibold ${accentText}`}>
                      Auto (regime-based)
                    </span>
                  </div>

                  <button onClick={handleStop} disabled={loading}
                    className="w-full bg-dark-600 border border-dark-500 text-gray-300 rounded-xl py-2.5 text-xs font-semibold flex items-center justify-center gap-2 hover:text-white hover:border-dark-400 transition-all disabled:opacity-40 mb-2">
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <Square size={12} />}
                    Stop Options {isLive ? 'Live' : 'Paper'} Swing
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
                  <div className="mb-3">
                    <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-2">Select Underlyings</h4>
                    <div className="space-y-1.5">
                      {UNDERLYING_OPTIONS.map(sym => {
                        const isSelected = !!selectedUnderlyings[sym]
                        return (
                          <button key={sym} onClick={() => toggleUnderlying(sym)}
                            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl border transition-all ${
                              isSelected ? `bg-dark-600 ${isLive ? 'border-emerald-500/30' : 'border-teal-500/30'}` : 'bg-dark-800 border-dark-600 hover:border-dark-500'
                            }`}>
                            <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border transition-all ${
                              isSelected ? accentCheck : 'border-gray-600 bg-dark-700'
                            }`}>
                              {isSelected && <Check size={10} className="text-white" />}
                            </div>
                            <span className="text-[11px] font-medium text-white">{sym}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div className="mb-3 bg-dark-600 rounded-xl px-3 py-2">
                    <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-1">Strategy Selection</h4>
                    <p className={`text-[11px] ${accentText} font-medium`}>Auto-selected by market regime</p>
                    <p className="text-[9px] text-gray-500 mt-0.5">Monthly expiry for swing positions</p>
                  </div>

                  <div className="relative group">
                    <button onClick={handleStart} disabled={loading || activeUnderlyings.length === 0}
                      className={`w-full bg-gradient-to-r ${accentGrad} text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed`}>
                      {loading ? (
                        <><Loader2 size={16} className="animate-spin" /> Starting...</>
                      ) : (
                        <><Play size={16} /> Start {isLive ? 'Live' : 'Paper'} Swing Auto</>
                      )}
                    </button>
                    <div className="absolute bottom-full left-0 right-0 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                      <div className="bg-dark-800 border border-dark-500 rounded-lg p-3 shadow-lg text-[10px] text-gray-400 leading-relaxed">
                        <p className="text-teal-400 font-semibold mb-1">Options Swing Auto Regime</p>
                        <p>Auto regime detection every scan. Monthly expiry spreads that carry overnight.</p>
                        <p className="mt-1">Scan: every 4h | Exit: SL / Target / 2d before expiry | Max 2 positions | Monthly expiry</p>
                      </div>
                    </div>
                  </div>

                  {isLive && (
                    <div className="mt-2 flex items-start gap-2 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
                      <ShieldAlert size={10} className="text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-[9px] text-red-400 leading-relaxed">
                        Live mode places real options orders on Fyers. Real money at risk. Positions carry overnight.
                      </p>
                    </div>
                  )}
                </>
              )}

              <div className="mt-3 flex items-start gap-2 px-1">
                <AlertTriangle size={10} className="text-gray-600 flex-shrink-0 mt-0.5" />
                <p className="text-[9px] text-gray-600 leading-relaxed">
                  Swing mode &bull; Auto regime-based strategy &bull; Monthly expiry &bull; Positions carry overnight &bull; {isLive ? 'Real orders via Fyers' : 'No real orders'}
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
    teal: 'bg-teal-500/10 text-teal-400',
    green: 'bg-green-500/10 text-green-400',
    gray: 'bg-gray-500/10 text-gray-400',
    yellow: 'bg-yellow-500/10 text-yellow-400',
    amber: 'bg-amber-500/10 text-amber-400',
    red: 'bg-red-500/10 text-red-400',
    orange: 'bg-orange-500/10 text-orange-400',
  }
  return (
    <span className={`text-[9px] font-medium px-2 py-0.5 rounded-full ${colors[color]}`}>
      {text}
    </span>
  )
}
