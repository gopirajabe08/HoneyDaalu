import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Loader2, Activity, Zap, FlaskConical,
  TrendingUp, TrendingDown, Target, RefreshCw, Sunrise, Clock
} from 'lucide-react'
import {
  startBTST, stopBTST, getBTSTStatus, startBTSTRegime,
  startBTSTPaper, stopBTSTPaper, getBTSTPaperStatus, startBTSTPaperRegime,
  getEquityRegime, getPositions, getTradeHistory,
} from '../services/api'
import CapitalInput from './CapitalInput'
import DailyStrategyStats from './DailyStrategyStats'
import { LOG_COLORS } from '../utils/constants'
import { formatINR } from '../utils/formatters'

const TABS = [
  { id: 'btst-paper', label: 'BTST Paper', icon: FlaskConical, color: 'amber' },
  { id: 'btst-live', label: 'BTST Live', icon: Zap, color: 'yellow' },
]

const TAB_COLORS = {
  amber: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  yellow: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
}

const TAB_CONFIG = {
  'btst-live': { start: startBTST, stop: stopBTST, status: getBTSTStatus, autoStart: startBTSTRegime, isLive: true },
  'btst-paper': { start: startBTSTPaper, stop: stopBTSTPaper, status: getBTSTPaperStatus, autoStart: startBTSTPaperRegime, isLive: false },
}

const POLL_INTERVAL = 10_000  // 10s

export default function BTSTPage({ capital, setCapital }) {
  const [activeTab, setActiveTab] = useState('btst-live')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const [autoMode, setAutoMode] = useState(true)
  const [regime, setRegime] = useState(null)
  const [brokerPositions, setBrokerPositions] = useState([])
  const pollRef = useRef(null)
  const logEndRef = useRef(null)

  const config = TAB_CONFIG[activeTab]
  const running = status?.is_running ?? false
  const isLive = config.isLive

  // Fetch regime on mount + refresh every 60s while running
  useEffect(() => { getEquityRegime().then(setRegime).catch(() => {}) }, [])
  useEffect(() => {
    if (!running) return
    const id = setInterval(() => { getEquityRegime().then(setRegime).catch(() => {}) }, 60000)
    return () => clearInterval(id)
  }, [running])

  // Poll status
  const pollStatus = useCallback(async () => {
    try {
      const data = await config.status()
      // If engine trade_history is empty, fetch from trade logger (survives restart)
      if (!data.trade_history || data.trade_history.length === 0) {
        try {
          const src = config.isLive ? 'btst' : 'btst_paper'
          const histRes = await getTradeHistory(1, src)
          const hist = Array.isArray(histRes) ? histRes : (histRes?.trades || [])
          if (hist.length > 0) data.trade_history = hist
        } catch {}
      }
      setStatus(data)
      // For live mode, fetch TradeJini CNC positions as source of truth
      if (config.isLive) {
        try {
          const posRes = await getPositions()
          const posArr = posRes?.netPositions || posRes?.data?.netPositions || []
          const cncOnly = posArr.filter(p => {
            const prod = (p.productType || '').toUpperCase()
            return prod === 'CNC' && ((p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
          })
          setBrokerPositions(cncOnly)
        } catch {}
      }
    } catch {}
  }, [activeTab])

  useEffect(() => { pollStatus() }, [pollStatus])

  // Always poll in live mode (CNC positions may exist even when engine stopped)
  useEffect(() => {
    if (running || isLive) {
      pollRef.current = setInterval(pollStatus, POLL_INTERVAL)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [running, isLive, pollStatus])

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [status?.logs])

  const handleStart = async () => {
    setLoading(true)
    setError('')

    try {
      let res
      if (autoMode) {
        res = await config.autoStart(capital)
        if (res?.regime) setRegime(res.regime)
      } else {
        // BTST uses auto mode primarily; manual fallback sends empty strategies
        res = await config.start([], capital)
      }
      if (res?.error) setError(res.error)
      else await pollStatus()
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      await config.stop()
      await pollStatus()
    } catch {}
    setLoading(false)
  }

  // Filter to CNC (BTST) positions only — exclude INTRADAY/BO product types
  const isCNCPosition = (t) => {
    // If productType is available, check for CNC
    if (t.productType) return t.productType === 'CNC'
    // BTST engine positions are CNC by definition, but also exclude options/futures symbols
    const sym = (t.symbol || '').toUpperCase()
    return !sym.includes('CE') && !sym.includes('PE') && !sym.includes('FUT')
  }
  const positions = (status?.active_trades || []).filter(isCNCPosition)
  const history = (status?.trade_history || []).filter(isCNCPosition)
  const logs = status?.logs || []

  // For live: use TradeJini P&L (source of truth). For paper: use engine P&L.
  const brokerTotalPnl = brokerPositions.reduce((s, p) => s + (p.pl || 0), 0)
  const totalPnl = isLive && brokerPositions.length > 0 ? brokerTotalPnl : (status?.total_pnl ?? 0)

  // Win/loss from trade history
  const allClosed = history
  const winners = allClosed.filter(t => (t.pnl ?? 0) > 0)
  const losers = allClosed.filter(t => (t.pnl ?? 0) < 0)
  const winRate = allClosed.length > 0 ? Math.round((winners.length / allClosed.length) * 100) : 0

  return (
    <div className="space-y-5">
      {/* Header + Tab bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sunrise size={22} className="text-amber-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">BTST Trading</h2>
            <p className="text-gray-500 text-xs">Buy Today Sell Tomorrow -- overnight positional trades on Nifty 500 stocks</p>
          </div>
        </div>

        <div className="flex items-center bg-dark-700 rounded-xl p-1 border border-dark-500">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setStatus(null) }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === tab.id
                  ? TAB_COLORS[tab.color]
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <tab.icon size={12} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Quick Start Guide */}
      <div className="flex items-center gap-3 bg-dark-700/30 rounded-lg px-4 py-1.5 border border-dark-600/50 text-[10px] text-gray-500">
        <span className="text-white font-semibold">Quick Start</span>
        <span className="text-dark-500">|</span>
        <span>Scan at <span className="text-amber-400 font-semibold">2:00 PM</span></span>
        <span className="text-dark-500">|</span>
        <span>Capital: <span className="text-white">₹1L</span> (paper)</span>
        <span className="text-dark-500">|</span>
        <span>Mode: <span className="text-amber-400">Auto Regime</span> (NIFTY + VIX)</span>
        <span className="text-dark-500">|</span>
        <span>Buy: 2:00 - 3:15 PM | Sell: next day 9:20 - 10:00 AM</span>
      </div>

      {/* Timing Reference */}
      <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-amber-500/10 text-[10px] text-gray-500">
        <span className="text-amber-400 font-semibold">BTST</span>
        <span className="text-dark-500">|</span>
        <span>Regime: <span className="text-amber-400">Auto</span> (NIFTY + VIX + ADX picks strategies)</span>
        <span className="text-dark-500">|</span>
        <span>Scan: <span className="text-amber-400">2:00 PM</span> (daily candle forming)</span>
        <span className="text-dark-500">|</span>
        <span>Buy: <span className="text-amber-400">2:00 - 3:15 PM</span> (CNC)</span>
        <span className="text-dark-500">|</span>
        <span>Sell: <span className="text-yellow-400">next day 9:20 - 10:00 AM</span></span>
        <span className="text-dark-500">|</span>
        <span>Monitor: <span className="text-white">every 60s</span></span>
        <span className="text-dark-500">|</span>
        <span>SL: <span className="text-white">min 1.5%</span></span>
        <span className="text-dark-500">|</span>
        <span>Target: <span className="text-white">2-3%</span></span>
        <span className="text-dark-500">|</span>
        <span>Risk: <span className="text-white">2%/trade</span></span>
        <span className="text-dark-500">|</span>
        <span>Daily loss: <span className="text-red-400">5% cap</span></span>
        <span className="text-dark-500">|</span>
        <span>Positions: <span className="text-white">{isLive ? '3 live' : '5 paper'}</span></span>
        <span className="text-dark-500">|</span>
        <span>Nifty 500 | ₹100-₹5,000</span>
      </div>

      {/* Market Regime */}
      {regime && (
        <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-gray-400">Market Regime</h3>
            <span className="text-[10px] text-gray-600">NIFTY + VIX Analysis</span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-bold text-amber-400">
              {(regime.regime || 'detecting...').replace(/_/g, ' ').toUpperCase()}
            </span>
            {regime.components?.vix > 0 && (
              <span className="text-xs text-gray-500">VIX: {regime.components.vix}</span>
            )}
            {regime.components?.nifty?.adx > 0 && (
              <span className="text-xs text-gray-500">ADX: {regime.components.nifty.adx}</span>
            )}
          </div>
          {regime.strategy_ids && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-gray-500">Auto-selected:</span>
              {regime.strategy_ids.map(s => (
                <span key={s} className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  {s.replace('play', 'P').replace('_', ' ').replace('ema crossover', 'EMA').replace('triple ma', 'Triple MA').replace('vwap pullback', 'VWAP').replace('supertrend', 'Supertrend').replace('bb squeeze', 'BB Squeeze').replace('bb contra', 'BB Contra')}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Strategy Selection + Capital (when stopped) */}
      {!running && (
        <div className={`bg-dark-700 rounded-xl p-5 border ${isLive ? 'border-yellow-500/20' : 'border-amber-500/20'}`}>
          {/* Auto / Manual Toggle */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Strategy Selection</h3>
            <div className="flex items-center gap-2 bg-dark-800 rounded-lg p-1 border border-dark-500">
              <button
                onClick={() => setAutoMode(true)}
                className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                  autoMode ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'text-gray-500'
                }`}
              >
                Auto (Regime)
              </button>
              <button
                onClick={() => setAutoMode(false)}
                className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                  !autoMode ? 'bg-gray-500/20 text-gray-300 border border-gray-500/30' : 'text-gray-500'
                }`}
              >
                Manual
              </button>
            </div>
          </div>

          {autoMode ? (
            <div className="bg-dark-800 rounded-lg p-4 border border-amber-500/10 mb-4">
              <p className="text-xs text-gray-400">
                Strategies will be <span className="text-amber-400 font-semibold">automatically selected</span> based on current market conditions:
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-gray-500">
                <li>Bullish trend + Low VIX -- EMA Crossover, Triple MA, Supertrend (BUY only)</li>
                <li>Strong momentum -- BB Squeeze breakout, VWAP pullback</li>
                <li>High VIX / Bearish -- Reduced position size, tighter SL</li>
                <li>Overnight risk managed via hard SL + target placement</li>
              </ul>
              {regime?.reasoning && (
                <p className="mt-3 text-[10px] text-amber-400/60 border-t border-dark-600 pt-2">
                  Current: {regime.reasoning}
                </p>
              )}
            </div>
          ) : (
            <div className="bg-dark-800 rounded-lg p-4 border border-dark-600 mb-4">
              <p className="text-xs text-gray-400">
                Manual mode: system scans with all eligible strategies and applies BTST filters (strong close, volume, trend alignment).
              </p>
            </div>
          )}

          <CapitalInput capital={capital} setCapital={setCapital} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Start/Stop */}
      <div className="flex gap-3">
        {!running ? (
          <div className="relative group">
            <button
              onClick={handleStart}
              disabled={loading}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm transition-all ${
                isLive
                  ? 'bg-gradient-to-r from-yellow-500 to-amber-500 text-white hover:shadow-lg hover:shadow-yellow-500/25'
                  : 'bg-gradient-to-r from-amber-500 to-emerald-500 text-white hover:shadow-lg hover:shadow-amber-500/25'
              }`}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              Start {isLive ? 'Live' : 'Paper'} BTST {autoMode ? 'Auto' : ''}
            </button>
            <div className="absolute bottom-full left-0 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 w-72">
              <div className="bg-dark-800 border border-dark-500 rounded-lg p-3 shadow-lg text-[10px] text-gray-400 leading-relaxed">
                {autoMode ? (
                  <>
                    <p className="text-amber-400 font-semibold mb-1">BTST Auto Regime</p>
                    <p>Detects NIFTY trend + VIX + ADX. Picks strategies automatically for overnight trades.</p>
                    <p className="mt-1">Scan: 2 PM | Buy: 2-3:15 PM (CNC) | Sell: next day 9:20-10 AM</p>
                    <p className="mt-1">Risk: 2%/trade | SL: min 1.5% | Target: 2-3% | Daily loss: 5% cap</p>
                  </>
                ) : (
                  <>
                    <p className="text-white font-semibold mb-1">BTST Manual Mode</p>
                    <p>System scans with all eligible strategies. BTST filters still active.</p>
                    <p className="mt-1">Scan: 2 PM | Buy: 2-3:15 PM (CNC) | Sell: next day 9:20-10 AM</p>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={handleStop}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Square size={16} />}
            Stop BTST
          </button>
        )}

        {running && (
          <button onClick={pollStatus} className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs text-gray-400 hover:text-white bg-dark-700 border border-dark-500">
            <RefreshCw size={12} />
            Refresh
          </button>
        )}
      </div>

      {/* Stats row */}
      {status && (
        <div className="grid grid-cols-6 gap-3">
          {[
            { label: 'Capital', value: status.capital > 0 ? `₹${(status.capital >= 100000 ? (status.capital/100000).toFixed(1)+'L' : (status.capital/1000).toFixed(0)+'K')}` : '--' },
            { label: 'Scans', value: status.scan_count || 0 },
            { label: 'Orders', value: status.order_count || 0 },
            { label: 'P&L', value: `${totalPnl >= 0 ? '+' : '-'}${formatINR(totalPnl)}`, color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400' },
            { label: 'Win Rate', value: allClosed.length > 0 ? `${winRate}%` : '--', sub: allClosed.length > 0 ? `${winners.length}W / ${losers.length}L` : '' },
            { label: 'Positions', value: `${positions.length} open` },
          ].map(s => (
            <div key={s.label} className="bg-dark-700 rounded-lg p-3 border border-dark-500">
              <div className="text-[10px] text-gray-500 mb-1">{s.label}</div>
              <div className={`text-sm font-bold ${s.color || 'text-white'}`}>{s.value}</div>
              {s.sub && <div className="text-[10px] text-gray-500">{s.sub}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Daily Loss Warning */}
      {status?.daily_loss_limit_hit && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-center gap-2">
          <span className="text-red-400 text-xs font-semibold">DAILY LOSS LIMIT HIT</span>
          <span className="text-red-400/70 text-xs">-- No new orders today. Daily P&L: ₹{(status.daily_realized_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
      )}

      {/* TradeJini CNC Positions (Source of Truth) — Live only */}
      {isLive && brokerPositions.length > 0 && (
        <div className="bg-dark-700 rounded-xl p-4 border border-emerald-500/30">
          <h3 className="text-xs font-semibold text-emerald-400 mb-3 flex items-center gap-2">
            <Activity size={14} />
            TradeJini CNC Positions (Source of Truth)
            <span className="text-[10px] text-gray-500 font-normal">{brokerPositions.length} position(s)</span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-500">
                  {['Symbol', 'Net Qty', 'Buy Avg', 'Sell Avg', 'LTP', 'P&L', 'Status'].map(h => (
                    <th key={h} className="text-[10px] text-gray-500 font-medium text-left py-2 px-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {brokerPositions.map((p, i) => {
                  const pnl = p.pl || 0
                  const sym = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
                  const netQty = p.netQty || 0
                  return (
                    <tr key={i} className="border-b border-dark-600/50 hover:bg-dark-600/30">
                      <td className="py-2 px-2 text-xs font-medium text-white">{sym}</td>
                      <td className="py-2 px-2 text-xs">{netQty}</td>
                      <td className="py-2 px-2 text-xs">₹{(p.buyAvg || 0).toFixed(2)}</td>
                      <td className="py-2 px-2 text-xs">₹{(p.sellAvg || 0).toFixed(2)}</td>
                      <td className="py-2 px-2 text-xs">₹{(p.ltp || 0).toFixed(2)}</td>
                      <td className={`py-2 px-2 text-xs font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pnl >= 0 ? '+' : ''}₹{pnl.toFixed(2)}
                      </td>
                      <td className="py-2 px-2 text-xs">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${netQty !== 0 ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-500/20 text-gray-400'}`}>
                          {netQty !== 0 ? 'HOLDING' : 'CLOSED'}
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

      {/* Active Positions */}
      {positions.length > 0 && (
        <div className="bg-dark-700 rounded-xl p-4 border border-amber-500/20">
          <h3 className="text-xs font-semibold text-gray-400 mb-3 flex items-center gap-2">
            <Activity size={14} className="text-amber-400" />
            Active BTST Positions
            <span className="text-[10px] text-gray-500 font-normal">{positions.length} open</span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-500">
                  {['Symbol', 'Strategy', 'Entry Price', 'SL', 'Target', 'LTP', 'P&L', 'Days Held', 'Status'].map(h => (
                    <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((t, i) => {
                  const pnl = t.pnl ?? 0
                  const isBuy = t.signal_type === 'BUY' || t.side === 1
                  const daysHeld = t.days_held ?? 0
                  return (
                    <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                      <td className="px-3 py-2.5 text-sm font-medium text-white">{t.symbol}</td>
                      <td className="px-3 py-2.5 text-[11px] text-gray-400">{t.strategy || '--'}</td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">{'\u20B9'}{t.entry_price}</td>
                      <td className="px-3 py-2.5 text-xs text-red-400">{'\u20B9'}{t.stop_loss}</td>
                      <td className="px-3 py-2.5 text-xs text-green-400">{'\u20B9'}{t.target}</td>
                      <td className="px-3 py-2.5 text-xs text-white font-medium">{'\u20B9'}{t.ltp || t.entry_price}</td>
                      <td className="px-3 py-2.5">
                        <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {pnl >= 0 ? '+' : '-'}{formatINR(pnl)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`text-xs font-semibold ${daysHeld >= 2 ? 'text-yellow-400' : 'text-white'}`}>
                          {daysHeld}d
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                          isBuy ? 'bg-amber-500/15 text-amber-400' : 'bg-blue-500/15 text-blue-400'
                        }`}>
                          {t.status || 'OPEN'}
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
      <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
        <h3 className="text-xs font-semibold text-gray-400 mb-3 flex items-center gap-2">
          <Clock size={14} className="text-gray-400" />
          Trade History
          <span className="text-[10px] text-gray-500 font-normal">{history.length} trades</span>
        </h3>
        {history.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-4">No completed BTST trades yet. Trades will appear here after exit.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-500">
                  {['Symbol', 'Signal', 'Strategy', 'Entry', 'Exit', 'Qty', 'P&L', 'Days Held', 'Result'].map(h => (
                    <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...history].reverse().map((t, i) => {
                  const isBuy = t.signal_type === 'BUY' || t.side === 1
                  const pnl = t.pnl ?? 0
                  const reason = t.exit_reason || ''
                  const daysHeld = t.days_held ?? 0
                  const resultColor = reason === 'TARGET_HIT' ? 'bg-green-500/15 text-green-400' :
                    reason === 'SL_HIT' ? 'bg-red-500/15 text-red-400' :
                    reason === 'PROFIT_TARGET' ? 'bg-green-500/15 text-green-400' :
                    reason === 'LOSS_LIMIT' ? 'bg-red-500/15 text-red-400' :
                    'bg-gray-500/15 text-gray-400'
                  const resultLabel = reason === 'TARGET_HIT' ? 'TARGET' :
                    reason === 'SL_HIT' ? 'SL HIT' :
                    reason === 'PROFIT_TARGET' ? 'PROFIT' :
                    reason === 'LOSS_LIMIT' ? 'LOSS' :
                    reason === 'SQUARE_OFF' ? 'SQ OFF' :
                    reason === 'NEXT_DAY_EXIT' ? 'NEXT DAY' :
                    reason || 'CLOSED'

                  return (
                    <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                      <td className="px-3 py-2.5 text-sm font-medium text-white">{t.symbol}</td>
                      <td className="px-3 py-2.5">
                        <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                          {isBuy ? <TrendingUp size={9} /> : <TrendingDown size={9} />}
                          {isBuy ? 'BUY' : 'SELL'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-[11px] text-gray-400">{t.strategy || '--'}</td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">{'\u20B9'}{t.entry_price}</td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">{'\u20B9'}{t.exit_price || t.ltp || '--'}</td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">{t.quantity}</td>
                      <td className="px-3 py-2.5">
                        <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {pnl >= 0 ? '+' : '-'}{formatINR(pnl)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`text-xs font-semibold ${daysHeld >= 2 ? 'text-yellow-400' : 'text-white'}`}>
                          {daysHeld}d
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

      {/* Daily Strategy Performance */}
      <DailyStrategyStats
        source={isLive ? 'btst' : 'btst_paper'}
        days={7}
        accent={isLive ? 'yellow' : 'amber'}
      />

      {/* Logs */}
      {logs.length > 0 && (
        <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
          <h3 className="text-xs font-semibold text-gray-400 mb-3">Logs</h3>
          <div className="max-h-60 overflow-y-auto font-mono text-[11px] space-y-0.5">
            {logs.map((log, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gray-600 shrink-0">{log.time?.split('T')[1]?.substring(0, 8) || log.timestamp || ''}</span>
                <span className={`shrink-0 font-semibold w-16 ${LOG_COLORS[log.level] || 'text-gray-400'}`}>[{log.level}]</span>
                <span className="text-gray-300">{log.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* Empty state */}
      {!running && positions.length === 0 && history.length === 0 && logs.length === 0 && (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-12 text-center">
          <Sunrise size={36} className="text-gray-600 mx-auto mb-3" />
          <h3 className="text-white font-semibold mb-1">BTST Trading</h3>
          <p className="text-gray-500 text-xs max-w-md mx-auto">
            {isLive
              ? 'Buy stocks today near close (2-3:15 PM) and sell tomorrow morning (9:20-10 AM) for overnight momentum profits.'
              : 'Virtual BTST trading with no real money. Same rules as live -- overnight positions tracked with paper P&L.'}
          </p>
        </div>
      )}

    </div>
  )
}
