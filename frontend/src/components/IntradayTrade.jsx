import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Loader2, AlertTriangle, Activity, Clock, Zap,
  ShieldAlert, Check, TrendingUp, TrendingDown, Target, RefreshCw
} from 'lucide-react'
import { strategies } from '../data/mockData'
import {
  startAutoTrading, stopAutoTrading, getAutoStatus,
  startPaperTrading, stopPaperTrading, getPaperStatus,
  getPositions, getEquityRegime,
  startAutoTradingRegime, startPaperTradingRegime,
} from '../services/api'
import CapitalInput from './CapitalInput'
import DailyStrategyStats from './DailyStrategyStats'
import { LOG_COLORS } from '../utils/constants'
import { formatINR } from '../utils/formatters'

const POLL_INTERVAL = 10 * 1000  // 10s — near real-time status

export default function IntradayTrade({ mode = 'live', capital, setCapital }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const pollRef = useRef(null)
  const logEndRef = useRef(null)

  const [selected, setSelected] = useState(() =>
    mode === 'live'
      ? { play3_vwap_pullback: '5m', play4_supertrend: '5m' }
      : { play1_ema_crossover: '15m', play6_bb_contra: '15m' }
  )
  const [refreshing, setRefreshing] = useState(false)
  const [fyersPositions, setFyersPositions] = useState([])
  const [autoMode, setAutoMode] = useState(true)
  const [regime, setRegime] = useState(null)

  const running = status?.is_running ?? false
  const selectedCount = Object.keys(selected).length

  const isLive = mode === 'live'
  const accent = isLive ? 'orange' : 'blue'
  const accentGrad = isLive
    ? 'from-orange-500 to-pink-500'
    : 'from-blue-500 to-cyan-500'
  const accentBorder = isLive ? 'border-orange-500/20' : 'border-blue-500/20'
  const accentBg = isLive
    ? 'from-orange-500/5 to-pink-500/5'
    : 'from-blue-500/5 to-cyan-500/5'
  const accentDot = isLive ? 'bg-green-400' : 'bg-blue-400'
  const accentText = isLive ? 'text-orange-400' : 'text-blue-400'
  const accentCheck = isLive ? 'bg-orange-500 border-orange-500' : 'bg-blue-500 border-blue-500'
  const accentSelected = isLive ? 'border-orange-500/30' : 'border-blue-500/30'
  const accentTfActive = isLive
    ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
    : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'

  const pollStatus = useCallback(async () => {
    try {
      const data = isLive ? await getAutoStatus() : await getPaperStatus()
      setStatus(data)
      // For live mode, also fetch Fyers positions as source of truth
      if (isLive) {
        try {
          const posRes = await getPositions()
          const posArr = posRes?.netPositions || posRes?.data?.netPositions || []
          const intraday = posArr.filter(p => p.productType === 'INTRADAY' && ((p.buyQty || 0) > 0 || (p.sellQty || 0) > 0))
          setFyersPositions(intraday)
        } catch {}
      }
    } catch {}
  }, [isLive])

  // Fetch regime on mount + refresh every 60s while running
  useEffect(() => { getEquityRegime().then(setRegime).catch(() => {}) }, [])
  useEffect(() => {
    if (!running) return
    const id = setInterval(() => { getEquityRegime().then(setRegime).catch(() => {}) }, 60000)
    return () => clearInterval(id)
  }, [running])

  // Poll on mount and when mode switches
  useEffect(() => { pollStatus() }, [pollStatus])

  // Poll every 10s — always for live (Fyers data), only when running for paper
  useEffect(() => {
    if (running || isLive) {
      pollRef.current = setInterval(pollStatus, POLL_INTERVAL)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [running, pollStatus])

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
    setLoading(true)
    setError('')
    try {
      let data
      if (autoMode) {
        // Auto mode: regime detector picks strategies
        data = isLive
          ? await startAutoTradingRegime(capital)
          : await startPaperTradingRegime(capital)
        if (data?.regime) setRegime(data.regime)
      } else {
        // Manual mode
        if (selectedCount === 0) { setLoading(false); return }
        const stratList = Object.entries(selected).map(([strategy, timeframe]) => ({ strategy, timeframe }))
        data = isLive
          ? await startAutoTrading(stratList, capital)
          : await startPaperTrading(stratList, capital)
      }
      if (data.error) {
        setError(data.error)
      } else {
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
      isLive ? await stopAutoTrading() : await stopPaperTrading()
      await pollStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const logs = status?.logs ?? []
  const activeTrades = status?.active_trades ?? []
  const tradeHistory = status?.trade_history ?? []
  const orderCutoff = status?.order_cutoff_passed ?? false
  const squaredOff = status?.squared_off ?? false
  const runningStrategies = status?.strategies ?? []

  // For live mode: use Fyers P&L (source of truth). For paper: use engine P&L.
  const fyersTotalPnl = fyersPositions.reduce((s, p) => s + (p.pl || 0), 0)
  const fyersOpenCount = fyersPositions.filter(p => (p.netQty || 0) !== 0).length
  const fyersClosedCount = fyersPositions.filter(p => (p.netQty || 0) === 0).length
  const totalPnl = isLive && fyersPositions.length > 0 ? fyersTotalPnl : (status?.total_pnl ?? 0)

  const allClosed = tradeHistory
  const winners = allClosed.filter(t => (t.pnl ?? 0) > 0)
  const losers = allClosed.filter(t => (t.pnl ?? 0) < 0)
  const winRate = allClosed.length > 0 ? Math.round((winners.length / allClosed.length) * 100) : 0

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Zap size={18} className={accentText} />
        <p className="text-gray-400 text-xs">
          {isLive ? 'Live auto-trading with real orders via Fyers' : 'Virtual auto-trading with no real money'}
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
              <StatCard label={isLive ? 'P&L (Fyers)' : 'Virtual P&L'} value={`${totalPnl >= 0 ? '+' : '-'}${formatINR(totalPnl)}`}
                color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
              <StatCard label="Win Rate" value={allClosed.length > 0 ? `${winRate}%` : '--'}
                sub={allClosed.length > 0 ? `${winners.length}W / ${losers.length}L` : ''} />
              <StatCard label="Scans" value={status?.scan_count ?? 0} />
              <StatCard label="Orders" value={status?.order_count ?? 0} />
              <StatCard label="Open" value={isLive ? fyersOpenCount : activeTrades.length} color={accentText} />
            </div>
          )}

          {/* Fyers Positions (Live mode — source of truth) */}
          {isLive && fyersPositions.length > 0 && (
            <div className="bg-dark-700 rounded-2xl border border-orange-500/20 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className="text-orange-400" />
                Fyers Positions (Source of Truth)
                <span className="text-[10px] text-gray-500 font-normal">{fyersOpenCount} open · {fyersClosedCount} closed · P&L: <span className={fyersTotalPnl >= 0 ? 'text-green-400' : 'text-red-400'}>{fyersTotalPnl >= 0 ? '+' : '-'}{formatINR(fyersTotalPnl)}</span></span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-dark-500">
                      {['Symbol', 'Side', 'Net Qty', 'Buy Avg', 'Sell Avg', 'LTP', 'P&L', 'Status'].map(h => (
                        <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {fyersPositions.map((p, i) => {
                      const sym = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
                      const netQty = p.netQty || 0
                      const pnl = p.pl || 0
                      const isOpen = netQty !== 0
                      const isBuy = (p.buyQty || 0) > (p.sellQty || 0)
                      return (
                        <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                          <td className="px-3 py-2.5 text-sm font-medium text-white">{sym}</td>
                          <td className="px-3 py-2.5">
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                              {isBuy ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-white font-semibold">{netQty}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{p.buyAvg > 0 ? `₹${p.buyAvg.toFixed(1)}` : '--'}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-300">{p.sellAvg > 0 ? `₹${p.sellAvg.toFixed(1)}` : '--'}</td>
                          <td className="px-3 py-2.5 text-xs text-white">₹{(p.ltp || 0).toFixed(1)}</td>
                          <td className="px-3 py-2.5">
                            <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pnl >= 0 ? '+' : '-'}{formatINR(pnl)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                              isOpen ? 'bg-blue-500/15 text-blue-400' : pnl > 0 ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'
                            }`}>
                              {isOpen ? 'OPEN' : pnl >= 0 ? 'PROFIT' : 'LOSS'}
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

          {/* Active trades — show for paper mode, hide for live (Fyers section above is source of truth) */}
          {!isLive && activeTrades.length > 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className={accentText} />
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
                          <td className="px-3 py-2.5 text-xs text-gray-300">{'\u20B9'}{t.entry_price}</td>
                          <td className="px-3 py-2.5 text-xs text-red-400">{'\u20B9'}{t.stop_loss}</td>
                          <td className="px-3 py-2.5 text-xs text-green-400">{'\u20B9'}{t.target}</td>
                          <td className="px-3 py-2.5 text-xs text-white font-medium">{'\u20B9'}{t.ltp || t.entry_price}</td>
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

          {/* Completed Trades — always visible */}
          {/* Completed Trades — always visible */}
          {!isLive && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Clock size={16} className="text-gray-400" />
                Completed Trades
                <span className="text-[10px] text-gray-500 font-normal">{tradeHistory.length} trades</span>
              </h3>
              {tradeHistory.length === 0 ? (
                <p className="text-xs text-gray-600 text-center py-4">No completed trades yet. Trades will appear here after SL, target, or square-off.</p>
              ) : (
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
                            <td className="px-3 py-2.5 text-xs text-gray-300">{'\u20B9'}{t.entry_price}</td>
                            <td className="px-3 py-2.5 text-xs text-gray-300">{'\u20B9'}{t.exit_price || t.ltp || '--'}</td>
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
              )}
            </div>
          )}

          {/* Daily Strategy Performance — right after completed trades */}
          <DailyStrategyStats source={isLive ? 'auto' : 'paper'} days={7} accent={accent} />

          {/* Empty state */}
          {!running && activeTrades.length === 0 && tradeHistory.length === 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-12 text-center">
              <Zap size={36} className="text-gray-600 mx-auto mb-3" />
              <h3 className="text-white font-semibold mb-1">Intraday Trading</h3>
              <p className="text-gray-500 text-xs max-w-md mx-auto">
                {isLive
                  ? 'Select strategies and click Start to begin live auto-trading with real orders via Fyers.'
                  : 'Select strategies and click Start to begin virtual auto-trading. Same rules as live — no money at risk.'}
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
                <Zap size={16} className={running ? 'text-green-400' : accentText} />
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
                  {/* Live Regime Banner */}
                  {regime && (
                    <div className="bg-gradient-to-r from-dark-600 to-dark-700 rounded-xl px-3 py-2.5 mb-3 border border-dark-500/50">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-bold text-orange-400 uppercase tracking-wider">Live Regime</span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                            regime.confidence === 'high' ? 'bg-emerald-500/20 text-emerald-400' :
                            regime.confidence === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-red-500/20 text-red-400'
                          }`}>
                            {(regime.regime || '').replace(/_/g, ' ').toUpperCase()}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {regime.components?.vix > 0 && (
                            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                              regime.components.vix > 20 ? 'bg-red-500/20 text-red-400' :
                              regime.components.vix > 16 ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-emerald-500/20 text-emerald-400'
                            }`}>
                              VIX {regime.components.vix}
                            </span>
                          )}
                          {regime.components?.nifty?.adx > 0 && (
                            <span className="text-[9px] text-gray-400">ADX {regime.components.nifty.adx}</span>
                          )}
                          {regime.confidence && (
                            <span className={`text-[9px] ${
                              regime.confidence === 'high' ? 'text-emerald-400' :
                              regime.confidence === 'medium' ? 'text-yellow-400' : 'text-red-400'
                            }`}>
                              ● {regime.confidence}
                            </span>
                          )}
                        </div>
                      </div>
                      {regime.components?.intraday && (
                        <div className="text-[9px] text-gray-400">
                          Intraday: <span className={regime.components.intraday.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                            NIFTY {regime.components.intraday.change_pct >= 0 ? '+' : ''}{regime.components.intraday.change_pct}%
                          </span>
                          {regime.components?.nifty?.trend && (
                            <span className="text-gray-500 ml-2">Daily: {regime.components.nifty.trend}</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

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
                    <Badge color={isLive ? 'green' : 'blue'} text={isLive ? 'Live Mode' : 'Virtual Mode'} />
                    {orderCutoff && <Badge color="yellow" text="No new orders (past 2:00 PM)" />}
                    {squaredOff && <Badge color="purple" text="Squared off" />}
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
                      <span className="text-[10px] text-gray-400">Scan mode</span>
                    </div>
                    <span className={`text-[10px] font-semibold ${orderCutoff ? 'text-gray-500' : accentText}`}>
                      {orderCutoff ? 'Cutoff passed — monitoring only' : 'On-demand — scans when slot opens'}
                    </span>
                  </div>

                  <button onClick={handleStop} disabled={loading}
                    className="w-full bg-dark-600 border border-dark-500 text-gray-300 rounded-xl py-2.5 text-xs font-semibold flex items-center justify-center gap-2 hover:text-white hover:border-dark-400 transition-all disabled:opacity-40 mb-2">
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <Square size={12} />}
                    Stop {isLive ? 'Auto' : 'Paper'}-Trading
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
                  {/* Auto / Manual Toggle */}
                  <div className="flex items-center gap-1 bg-dark-800 rounded-lg p-1 border border-dark-600 mb-3">
                    <button onClick={() => setAutoMode(true)}
                      className={`flex-1 px-2 py-1.5 rounded-md text-[10px] font-semibold transition-all ${
                        autoMode ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'text-gray-500'
                      }`}>
                      Auto (Regime)
                    </button>
                    <button onClick={() => setAutoMode(false)}
                      className={`flex-1 px-2 py-1.5 rounded-md text-[10px] font-semibold transition-all ${
                        !autoMode ? 'bg-gray-500/20 text-gray-300 border border-gray-500/30' : 'text-gray-500'
                      }`}>
                      Manual
                    </button>
                  </div>

                  {autoMode ? (
                    <div className="mb-3">
                      <div className="bg-dark-800 rounded-lg p-3 border border-amber-500/10 mb-2">
                        <p className="text-[10px] text-gray-400 mb-1.5">
                          System auto-selects strategies based on <span className="text-amber-400 font-semibold">NIFTY trend + VIX + ADX</span>
                        </p>
                        {regime && (
                          <>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-[10px] font-bold text-amber-400">
                                {(regime.regime || '').replace(/_/g, ' ').toUpperCase()}
                              </span>
                              {regime.components?.vix > 0 && <span className="text-[9px] text-gray-500">VIX: {regime.components.vix}</span>}
                              {regime.components?.nifty?.adx > 0 && <span className="text-[9px] text-gray-500">ADX: {regime.components.nifty.adx}</span>}
                            </div>
                            {regime.strategy_ids && (
                              <div className="flex flex-wrap gap-1">
                                {regime.strategy_ids.map(s => (
                                  <span key={s} className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                    {s.replace('play', 'P').replace('_', ' ').replace('ema crossover', 'EMA').replace('triple ma', 'Triple MA').replace('vwap pullback', 'VWAP').replace('supertrend', 'Supertrend').replace('bb squeeze', 'BB Squeeze').replace('bb contra', 'BB Contra')}
                                  </span>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="mb-3">
                      <h4 className="text-[10px] text-gray-500 uppercase font-medium mb-2">Select Strategies</h4>
                      <div className="space-y-1.5">
                        {strategies.filter(s => isLive || !['play3_vwap_pullback', 'play4_supertrend'].includes(s.id)).map(strat => {
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
                                  {strat.timeframes.map(tf => (
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
                  )}

                  <div className="relative group">
                    <button onClick={handleStart} disabled={loading || (!autoMode && selectedCount === 0)}
                      className={`w-full bg-gradient-to-r ${accentGrad} text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed`}>
                      {loading ? (
                        <><Loader2 size={16} className="animate-spin" /> Starting...</>
                      ) : (
                        <><Play size={16} /> Start {isLive ? 'Live' : 'Paper'} {autoMode ? 'Auto' : `(${selectedCount})`}</>
                      )}
                    </button>
                    <div className="absolute bottom-full left-0 right-0 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                      <div className="bg-dark-800 border border-dark-500 rounded-lg p-3 shadow-lg text-[10px] text-gray-400 leading-relaxed">
                        {autoMode ? (
                          <>
                            <p className="text-amber-400 font-semibold mb-1">Auto Regime Mode</p>
                            <p>System detects NIFTY trend + VIX + ADX and picks the best strategies automatically.</p>
                            <p className="mt-1">Orders: 10:30 AM - 2 PM | Square-off: 3:15 PM | Max 2 orders/scan | SL min 1.2% | Trailing SL (paper) | Daily loss limit 5% | Drawdown breaker 15%/5d</p>
                            {isLive && <p className="mt-1">VIX {'>'} 18: skips 5m, uses 15m only | Orders verified on Fyers before tracking</p>}
                          </>
                        ) : (
                          <>
                            <p className="text-white font-semibold mb-1">Manual Mode</p>
                            <p>You pick strategies and timeframes. Engine scans at 10:30 AM, re-scans when slot opens.</p>
                            <p className="mt-1">Orders: 10:30 AM - 2 PM | Square-off: 3:15 PM | Max 2 orders/scan | SL min 1.2%</p>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {isLive && (
                    <div className="mt-2 flex items-start gap-2 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
                      <ShieldAlert size={10} className="text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-[9px] text-red-400 leading-relaxed">
                        Live mode places real orders on Fyers. Real money at risk.
                      </p>
                    </div>
                  )}
                </>
              )}

              <div className="mt-3 flex items-start gap-2 px-1">
                <AlertTriangle size={10} className="text-gray-600 flex-shrink-0 mt-0.5" />
                <p className="text-[9px] text-gray-600 leading-relaxed">
                  {isLive
                    ? 'Max 6 positions \u2022 2% risk \u2022 Orders 10:30 AM-2:00 PM \u2022 Square-off 3:15 PM'
                    : 'Virtual mode \u2022 Max 10 positions \u2022 2% risk \u2022 Trailing SL \u2022 Orders 10:30 AM-2:00 PM \u2022 No real orders placed'}
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
    orange: 'bg-orange-500/10 text-orange-400',
  }
  return (
    <span className={`text-[9px] font-medium px-2 py-0.5 rounded-full ${colors[color]}`}>
      {text}
    </span>
  )
}
