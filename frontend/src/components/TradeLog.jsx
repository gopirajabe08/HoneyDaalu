import React, { useState, useEffect } from 'react'
import { RefreshCw, ScrollText, Calendar, X, ChevronDown, Zap, BookOpen } from 'lucide-react'
import {
  getTradeHistory, getAutoStatus, getPaperStatus,
  getSwingStatus, getSwingPaperStatus,
  getOptionsAutoStatus, getOptionsPaperStatus,
  getOptionsSwingStatus, getOptionsSwingPaperStatus,
  getFuturesAutoStatus, getFuturesPaperStatus,
  getFuturesSwingStatus, getFuturesSwingPaperStatus,
} from '../services/api'
import { LOG_COLORS } from '../utils/constants'

const STRATEGY_NAMES = {
  play1: 'EMA Crossover', play1_ema_crossover: 'EMA Crossover',
  play2: 'Triple MA', play2_triple_ma: 'Triple MA',
  play3: 'VWAP Pullback', play3_vwap_pullback: 'VWAP Pullback',
  play4: 'Supertrend', play4_supertrend: 'Supertrend',
  play5: 'BB Squeeze', play5_bb_squeeze: 'BB Squeeze',
  play6: 'BB Contra', play6_bb_contra: 'BB Contra',
  bull_call_spread: 'Bull Call Spread',
  bull_put_spread: 'Bull Put Spread',
  bear_call_spread: 'Bear Call Spread',
  bear_put_spread: 'Bear Put Spread',
  iron_condor: 'Iron Condor',
  long_straddle: 'Long Straddle',
  futures_volume_breakout: 'Fut Vol Breakout',
  futures_candlestick_reversal: 'Fut Reversal',
  futures_mean_reversion: 'Fut Mean Rev',
  futures_ema_rsi_pullback: 'Fut EMA Pullback',
}

const STRATEGY_COLORS = {
  play1: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  play2: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  play3: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  play4: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  play5: 'bg-green-500/15 text-green-400 border-green-500/30',
  play6: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  play1_ema_crossover: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  play2_triple_ma: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  play3_vwap_pullback: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  play4_supertrend: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  play5_bb_squeeze: 'bg-green-500/15 text-green-400 border-green-500/30',
  play6_bb_contra: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  bull_call_spread: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  bull_put_spread: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  bear_call_spread: 'bg-red-500/15 text-red-400 border-red-500/30',
  bear_put_spread: 'bg-red-500/15 text-red-400 border-red-500/30',
  iron_condor: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
  long_straddle: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  futures_volume_breakout: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  futures_candlestick_reversal: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  futures_mean_reversion: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
  futures_ema_rsi_pullback: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
}

// Live source keys (real money engines)
const LIVE_SOURCES = new Set(['auto', 'swing', 'options_auto', 'options_swing', 'futures_auto', 'futures_swing'])
// Paper source keys
const PAPER_SOURCES = new Set(['paper', 'swing_paper', 'options_paper', 'options_swing_paper', 'futures_paper', 'futures_swing_paper'])

// Charges estimate: ~₹65 per executed trade (brokerage + STT + exchange + GST + stamp for a typical intraday equity trade)
const CHARGES_PER_TRADE = 65

export default function TradeLog() {
  const [trades, setTrades] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [days, setDays] = useState(7)
  const [liveMode, setLiveMode] = useState('ALL') // 'ALL', 'LIVE', 'PAPER'
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [strategyFilter, setStrategyFilter] = useState('ALL')
  const [logFilter, setLogFilter] = useState('ALL')
  const [tab, setTab] = useState('trades')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  useEffect(() => { refresh() }, [days])

  async function refresh() {
    setLoading(true)
    try {
      const emptyLogs = { logs: [] }
      const [history, autoData, paperData, swingData, swingPaperData,
             optAutoData, optPaperData, optSwingData, optSwingPaperData,
             futAutoData, futPaperData, futSwingData, futSwingPaperData] = await Promise.all([
        getTradeHistory(days).catch(() => []),
        getAutoStatus().catch(() => emptyLogs),
        getPaperStatus().catch(() => emptyLogs),
        getSwingStatus().catch(() => emptyLogs),
        getSwingPaperStatus().catch(() => emptyLogs),
        getOptionsAutoStatus().catch(() => emptyLogs),
        getOptionsPaperStatus().catch(() => emptyLogs),
        getOptionsSwingStatus().catch(() => emptyLogs),
        getOptionsSwingPaperStatus().catch(() => emptyLogs),
        getFuturesAutoStatus().catch(() => emptyLogs),
        getFuturesPaperStatus().catch(() => emptyLogs),
        getFuturesSwingStatus().catch(() => emptyLogs),
        getFuturesSwingPaperStatus().catch(() => emptyLogs),
      ])
      setTrades(Array.isArray(history) ? history : [])
      // Merge logs from all 12 engines
      const tagLogs = (data, source) => (data.logs || []).map(l => ({ ...l, source }))
      const combined = [
        ...tagLogs(autoData, 'auto'), ...tagLogs(paperData, 'paper'),
        ...tagLogs(swingData, 'swing'), ...tagLogs(swingPaperData, 'swing_paper'),
        ...tagLogs(optAutoData, 'options_auto'), ...tagLogs(optPaperData, 'options_paper'),
        ...tagLogs(optSwingData, 'options_swing'), ...tagLogs(optSwingPaperData, 'options_swing_paper'),
        ...tagLogs(futAutoData, 'futures_auto'), ...tagLogs(futPaperData, 'futures_paper'),
        ...tagLogs(futSwingData, 'futures_swing'), ...tagLogs(futSwingPaperData, 'futures_swing_paper'),
      ].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
      setLogs(combined)
    } catch {}
    setLoading(false)
  }

  // Source key → match value mapping
  const SOURCE_MATCH = {
    AUTO: 'auto', SWING: 'swing', PAPER: 'paper', SWING_PAPER: 'swing_paper',
    OPTIONS_AUTO: 'options_auto', OPTIONS_PAPER: 'options_paper',
    OPTIONS_SWING: 'options_swing', OPTIONS_SWING_PAPER: 'options_swing_paper',
    FUTURES_AUTO: 'futures_auto', FUTURES_PAPER: 'futures_paper',
    FUTURES_SWING: 'futures_swing', FUTURES_SWING_PAPER: 'futures_swing_paper',
  }

  // Filter trades
  const filteredTrades = trades.filter(t => {
    const src = t.source || ''
    // Live/Paper quick toggle
    if (liveMode === 'LIVE' && !LIVE_SOURCES.has(src)) return false
    if (liveMode === 'PAPER' && !PAPER_SOURCES.has(src)) return false
    if (sourceFilter !== 'ALL' && src !== SOURCE_MATCH[sourceFilter]) return false
    if (strategyFilter !== 'ALL' && t.strategy !== strategyFilter) return false
    const tradeDate = t.date || (t.closed_at || t.placed_at || '').split('T')[0]
    if (dateFrom && tradeDate < dateFrom) return false
    if (dateTo && tradeDate > dateTo) return false
    return true
  })

  // Sort trades by date descending
  const sortedTrades = [...filteredTrades].sort((a, b) =>
    (b.closed_at || b.placed_at || '').localeCompare(a.closed_at || a.placed_at || '')
  )

  // Compute charges for each trade: use existing charges if present, else estimate for live trades
  const tradesWithCharges = sortedTrades.map(t => {
    const src = t.source || ''
    const isLiveTrade = LIVE_SOURCES.has(src)
    const charges = (t.charges || 0) > 0 ? t.charges : (isLiveTrade ? CHARGES_PER_TRADE : 0)
    const pnl = t.pnl || 0
    const netPnl = t.net_pnl ?? (pnl - charges)
    return { ...t, _charges: charges, _netPnl: netPnl, _isLive: isLiveTrade }
  })

  // Stats from filtered trades
  const totalPnl = tradesWithCharges.reduce((s, t) => s + (t.pnl || 0), 0)
  const totalCharges = tradesWithCharges.reduce((s, t) => s + t._charges, 0)
  const totalNetPnl = totalPnl - totalCharges
  const wins = tradesWithCharges.filter(t => (t.pnl || 0) > 0).length
  const losses = tradesWithCharges.filter(t => (t.pnl || 0) < 0).length
  const winRate = tradesWithCharges.length > 0 ? ((wins / tradesWithCharges.length) * 100).toFixed(1) : '0.0'

  // Log filters
  const logFilters = ['ALL', 'ORDER', 'SCAN', 'ALERT', 'ERROR']
  const filteredLogs = logFilter === 'ALL' ? logs : logs.filter(l => l.level === logFilter)

  // Get unique strategies from trades
  const strategiesInTrades = [...new Set(trades.map(t => t.strategy).filter(Boolean))]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <ScrollText size={18} className="text-emerald-400" />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Trade Log</h2>
          {/* Live / Paper / All quick toggle */}
          <div className="flex items-center rounded-xl border p-0.5" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
            <button
              onClick={() => setLiveMode('ALL')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                liveMode === 'ALL' ? 'bg-dark-500 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setLiveMode('LIVE')}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                liveMode === 'LIVE' ? 'bg-emerald-500/15 text-emerald-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <Zap size={10} /> Live
            </button>
            <button
              onClick={() => setLiveMode('PAPER')}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                liveMode === 'PAPER' ? 'bg-blue-500/15 text-blue-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <BookOpen size={10} /> Paper
            </button>
          </div>
        </div>
        <button onClick={refresh} disabled={loading} className="text-gray-500 hover:text-gray-300 transition-colors">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-4">
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Gross P&L</p>
          <p className={`text-lg font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{totalPnl.toFixed(0)}
          </p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Charges</p>
          <p className="text-lg font-bold text-yellow-400">
            {'\u20B9'}{totalCharges.toFixed(0)}
          </p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Net P&L</p>
          <p className={`text-lg font-bold ${totalNetPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalNetPnl >= 0 ? '+' : ''}{'\u20B9'}{totalNetPnl.toFixed(0)}
          </p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Win Rate</p>
          <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{winRate}%</p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Wins / Losses</p>
          <p className="text-lg font-bold">
            <span className="text-green-400">{wins}</span>
            <span className="text-gray-600 mx-1">/</span>
            <span className="text-red-400">{losses}</span>
          </p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Total Trades</p>
          <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{tradesWithCharges.length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab('trades')}
          className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
            tab === 'trades'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              : 'bg-dark-700 text-gray-400 border border-dark-500 hover:text-gray-300'
          }`}
        >
          Trade History ({sortedTrades.length})
        </button>
        <button
          onClick={() => setTab('logs')}
          className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
            tab === 'logs'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              : 'bg-dark-700 text-gray-400 border border-dark-500 hover:text-gray-300'
          }`}
        >
          Engine Logs ({logs.length})
        </button>
      </div>

      {tab === 'trades' && (
        <>
          {/* Filters — single line: Source dropdown, Strategy dropdown, Date dropdown + range */}
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            {/* Source dropdown */}
            <div className="relative">
              <select
                value={sourceFilter}
                onChange={e => setSourceFilter(e.target.value)}
                className={`appearance-none pl-3 pr-7 py-1.5 rounded-lg text-[11px] font-medium border outline-none cursor-pointer transition-all ${
                  sourceFilter !== 'ALL'
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                    : 'bg-dark-700 text-gray-400 border-dark-500 hover:border-dark-400'
                }`}
              >
                <option value="ALL">All Sources</option>
                <option value="AUTO">Equity Intraday Live</option>
                <option value="PAPER">Equity Intraday Paper</option>
                <option value="SWING">Equity Swing Live</option>
                <option value="SWING_PAPER">Equity Swing Paper</option>
                <option value="OPTIONS_AUTO">Options Intraday Live</option>
                <option value="OPTIONS_PAPER">Options Intraday Paper</option>
                <option value="OPTIONS_SWING">Options Swing Live</option>
                <option value="OPTIONS_SWING_PAPER">Options Swing Paper</option>
                <option value="FUTURES_AUTO">Futures Intraday Live</option>
                <option value="FUTURES_PAPER">Futures Intraday Paper</option>
                <option value="FUTURES_SWING">Futures Swing Live</option>
                <option value="FUTURES_SWING_PAPER">Futures Swing Paper</option>
              </select>
              <ChevronDown size={10} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>

            {/* Strategy dropdown */}
            <div className="relative">
              <select
                value={strategyFilter}
                onChange={e => setStrategyFilter(e.target.value)}
                className={`appearance-none pl-3 pr-7 py-1.5 rounded-lg text-[11px] font-medium border outline-none cursor-pointer transition-all ${
                  strategyFilter !== 'ALL'
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                    : 'bg-dark-700 text-gray-400 border-dark-500 hover:border-dark-400'
                }`}
              >
                <option value="ALL">All Strategies</option>
                {strategiesInTrades.map(s => (
                  <option key={s} value={s}>{STRATEGY_NAMES[s] || s}</option>
                ))}
              </select>
              <ChevronDown size={10} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>

            {/* Date presets */}
            <div className="flex items-center gap-1 bg-dark-700 rounded-lg border border-dark-500 px-1.5 py-0.5">
              {[1, 7, 14, 30, 90].map(d => (
                <button
                  key={d}
                  onClick={() => { setDays(d); setDateFrom(''); setDateTo('') }}
                  className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                    days === d && !dateFrom && !dateTo
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {d === 1 ? 'Today' : `${d}d`}
                </button>
              ))}
            </div>

            {/* Date range picker */}
            <div className="flex items-center gap-1.5 bg-dark-700 rounded-lg border border-dark-500 px-2 py-1">
              <Calendar size={11} className="text-gray-500" />
              <input
                type="date"
                value={dateFrom}
                onChange={e => { setDateFrom(e.target.value); if (!dateTo) setDays(90) }}
                className="bg-transparent text-[10px] text-gray-300 outline-none w-[100px] [color-scheme:dark]"
              />
              <span className="text-gray-600 text-[10px]">-</span>
              <input
                type="date"
                value={dateTo}
                onChange={e => { setDateTo(e.target.value); if (!dateFrom) setDays(90) }}
                className="bg-transparent text-[10px] text-gray-300 outline-none w-[100px] [color-scheme:dark]"
              />
              {(dateFrom || dateTo) && (
                <button onClick={() => { setDateFrom(''); setDateTo('') }} className="text-gray-500 hover:text-red-400">
                  <X size={10} />
                </button>
              )}
            </div>

            {/* Clear all */}
            {(sourceFilter !== 'ALL' || strategyFilter !== 'ALL' || dateFrom || dateTo || liveMode !== 'ALL') && (
              <button
                onClick={() => { setSourceFilter('ALL'); setStrategyFilter('ALL'); setDateFrom(''); setDateTo(''); setDays(7); setLiveMode('ALL') }}
                className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] text-red-400 hover:bg-red-500/10 transition-all"
              >
                <X size={10} /> Clear All
              </button>
            )}
          </div>

          {/* Trade Table */}
          <div className="rounded-2xl border p-5" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
            {tradesWithCharges.length === 0 ? (
              <p className="text-xs text-center py-8" style={{ color: 'var(--text-secondary)' }}>
                No trades in the last {days} days{liveMode !== 'ALL' ? ` (${liveMode.toLowerCase()} only)` : ''}. Start auto-trading or paper trading to see history.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr style={{ borderBottomWidth: '1px', borderColor: 'var(--border)' }}>
                      <th className="text-left text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Date</th>
                      <th className="text-left text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Symbol</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Strategy</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Source</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Type</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Entry</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Exit</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Qty</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>P&L</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Charges</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Net P&L</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Exit Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tradesWithCharges.map((t, i) => {
                      const stratKey = t.strategy || ''
                      const stratColor = STRATEGY_COLORS[stratKey] || 'bg-gray-500/15 text-gray-400 border-gray-500/30'
                      const pnl = t.pnl || 0
                      const exitPrice = t.exit_price || t.ltp || '-'
                      const date = (t.closed_at || t.placed_at || '').split('T')[0]
                      const time = (t.closed_at || t.placed_at || '').split('T')[1]?.substring(0, 8) || ''
                      const exitReason = t.exit_reason || '-'
                      const exitReasonColor =
                        exitReason === 'TARGET_HIT' ? 'text-green-400' :
                        exitReason === 'SL_HIT' ? 'text-red-400' :
                        exitReason === 'SQUARE_OFF' ? 'text-purple-400' : 'text-gray-400'
                      // Live trade highlight, paper trade dim
                      const rowOpacity = t._isLive ? '' : 'opacity-60'
                      const rowBorder = t._isLive ? 'border-l-2 border-l-emerald-500/40' : ''

                      return (
                        <tr key={i} className={`border-b border-dark-600/50 hover:bg-dark-600/30 ${rowOpacity} ${rowBorder}`}>
                          <td className="py-2">
                            <div className="text-xs" style={{ color: 'var(--text-primary)' }}>{date}</div>
                            <div className="text-[10px] text-gray-500">{time}</div>
                          </td>
                          <td className="py-2 text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{t.symbol}</td>
                          <td className="py-2 text-center">
                            {stratKey ? (
                              <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${stratColor}`}>
                                {STRATEGY_NAMES[stratKey] || stratKey}
                              </span>
                            ) : (
                              <span className="text-[9px] text-gray-600">-</span>
                            )}
                          </td>
                          <td className="py-2 text-center">
                            <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${
                              t.source === 'auto' ? 'bg-emerald-500/15 text-emerald-400' :
                              t.source === 'swing' ? 'bg-emerald-500/15 text-emerald-400' :
                              t.source === 'swing_paper' ? 'bg-teal-500/15 text-teal-400' :
                              t.source === 'options_auto' ? 'bg-violet-500/15 text-violet-400' :
                              t.source === 'options_paper' ? 'bg-indigo-500/15 text-indigo-400' :
                              t.source === 'options_swing' ? 'bg-purple-500/15 text-purple-400' :
                              t.source === 'options_swing_paper' ? 'bg-fuchsia-500/15 text-fuchsia-400' :
                              t.source === 'futures_auto' ? 'bg-amber-500/15 text-amber-400' :
                              t.source === 'futures_paper' ? 'bg-yellow-500/15 text-yellow-400' :
                              t.source === 'futures_swing' ? 'bg-lime-500/15 text-lime-400' :
                              t.source === 'futures_swing_paper' ? 'bg-cyan-500/15 text-cyan-400' :
                              'bg-blue-500/15 text-blue-400'
                            }`}>
                              {{ auto: 'EQ-LIVE', paper: 'EQ-PAPER', swing: 'EQ-SWING', swing_paper: 'EQ-SW-PAP',
                                 options_auto: 'OPT-LIVE', options_paper: 'OPT-PAPER', options_swing: 'OPT-SWING', options_swing_paper: 'OPT-SW-PAP',
                                 futures_auto: 'FUT-LIVE', futures_paper: 'FUT-PAPER', futures_swing: 'FUT-SWING', futures_swing_paper: 'FUT-SW-PAP',
                              }[t.source] || t.source}
                            </span>
                          </td>
                          <td className="py-2 text-center">
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              t.signal_type === 'BUY'
                                ? 'bg-green-500/15 text-green-400'
                                : 'bg-red-500/15 text-red-400'
                            }`}>
                              {t.signal_type}
                            </span>
                          </td>
                          <td className="py-2 text-right text-xs" style={{ color: 'var(--text-primary)' }}>
                            {'\u20B9'}{Number(t.entry_price).toFixed(2)}
                          </td>
                          <td className="py-2 text-right text-xs" style={{ color: 'var(--text-primary)' }}>
                            {exitPrice !== '-' ? `\u20B9${Number(exitPrice).toFixed(2)}` : '-'}
                          </td>
                          <td className="py-2 text-right text-xs" style={{ color: 'var(--text-primary)' }}>{t.quantity}</td>
                          <td className={`py-2 text-right text-xs font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {pnl >= 0 ? '+' : ''}{'\u20B9'}{pnl.toFixed(2)}
                          </td>
                          <td className="py-2 text-right text-xs text-yellow-400/70">
                            {t._charges > 0 ? `\u20B9${t._charges.toFixed(0)}` : '-'}
                          </td>
                          <td className={`py-2 text-right text-xs font-semibold ${t._netPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {t._netPnl >= 0 ? '+' : ''}{'\u20B9'}{t._netPnl.toFixed(2)}
                          </td>
                          <td className={`py-2 text-center text-[9px] font-medium ${exitReasonColor}`}>
                            {exitReason.replace('_', ' ')}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                  {/* Totals Footer */}
                  <tfoot>
                    <tr className="border-t-2 border-dark-400">
                      <td colSpan={4} className="py-2.5 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Total ({tradesWithCharges.length} trades)
                      </td>
                      <td className="py-2.5 text-center text-[10px] text-gray-500">
                        <span className="text-green-400">{wins}W</span>
                        <span className="text-gray-600 mx-0.5">/</span>
                        <span className="text-red-400">{losses}L</span>
                      </td>
                      <td />
                      <td />
                      <td className="py-2.5 text-right text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                        {tradesWithCharges.reduce((s, t) => s + (t.quantity || 0), 0)}
                      </td>
                      <td className={`py-2.5 text-right text-xs font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{totalPnl.toFixed(2)}
                      </td>
                      <td className="py-2.5 text-right text-xs font-bold text-yellow-400">
                        {'\u20B9'}{totalCharges.toFixed(0)}
                      </td>
                      <td className={`py-2.5 text-right text-xs font-bold ${totalNetPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {totalNetPnl >= 0 ? '+' : ''}{'\u20B9'}{totalNetPnl.toFixed(2)}
                      </td>
                      <td className="py-2.5 text-center text-[10px] text-gray-500 font-medium">
                        {winRate}% win
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {tab === 'logs' && (
        <>
          {/* Log Filters */}
          <div className="flex gap-2 mb-3">
            {logFilters.map(f => (
              <button
                key={f}
                onClick={() => setLogFilter(f)}
                className={`px-3 py-1 rounded-lg text-[10px] font-medium transition-all ${
                  logFilter === f
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-dark-700 text-gray-400 border border-dark-500 hover:text-gray-300'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Full Log */}
          <div className="bg-dark-700 rounded-2xl border border-dark-500 overflow-hidden">
            <div className="bg-dark-800 p-4 max-h-[500px] overflow-y-auto font-mono">
              {filteredLogs.length === 0 ? (
                <p className="text-xs text-gray-600 text-center py-8">No log entries yet. Start auto-trading or paper trading to see activity.</p>
              ) : (
                filteredLogs.map((entry, i) => (
                  <div key={i} className="flex gap-3 text-[11px] leading-relaxed py-0.5 hover:bg-dark-700/50 px-2 rounded">
                    <span className="text-gray-600 flex-shrink-0 tabular-nums w-16">{entry.timestamp}</span>
                    <span className={`flex-shrink-0 font-bold w-20 ${LOG_COLORS[entry.level] || 'text-gray-400'}`}>
                      [{entry.level}]
                    </span>
                    <span className={`flex-shrink-0 text-[9px] font-medium px-1 py-0.5 rounded min-w-[50px] text-center ${
                      entry.source === 'auto' ? 'bg-emerald-500/10 text-emerald-400' :
                      entry.source === 'swing' ? 'bg-emerald-500/10 text-emerald-400' :
                      entry.source === 'swing_paper' ? 'bg-teal-500/10 text-teal-400' :
                      entry.source === 'options_auto' ? 'bg-violet-500/10 text-violet-400' :
                      entry.source === 'options_paper' ? 'bg-indigo-500/10 text-indigo-400' :
                      entry.source === 'options_swing' ? 'bg-purple-500/10 text-purple-400' :
                      entry.source === 'options_swing_paper' ? 'bg-fuchsia-500/10 text-fuchsia-400' :
                      entry.source === 'futures_auto' ? 'bg-amber-500/10 text-amber-400' :
                      entry.source === 'futures_paper' ? 'bg-yellow-500/10 text-yellow-400' :
                      entry.source === 'futures_swing' ? 'bg-lime-500/10 text-lime-400' :
                      entry.source === 'futures_swing_paper' ? 'bg-cyan-500/10 text-cyan-400' :
                      'bg-blue-500/10 text-blue-400'
                    }`}>
                      {{ auto: 'EQ-LV', paper: 'EQ-PP', swing: 'EQ-SW', swing_paper: 'EQ-SP',
                         options_auto: 'OPT-LV', options_paper: 'OPT-PP', options_swing: 'OPT-SW', options_swing_paper: 'OPT-SP',
                         futures_auto: 'FUT-LV', futures_paper: 'FUT-PP', futures_swing: 'FUT-SW', futures_swing_paper: 'FUT-SP',
                      }[entry.source] || entry.source}
                    </span>
                    <span className="text-gray-300">{entry.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
