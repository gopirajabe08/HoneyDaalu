import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Loader2, Activity, Zap, FlaskConical, Repeat,
  TrendingUp, TrendingDown, Target, RefreshCw, BarChart3
} from 'lucide-react'
import {
  getFuturesStrategies, getFuturesRegime,
  startFuturesAutoTrading, stopFuturesAutoTrading, getFuturesAutoStatus,
  startFuturesPaperTrading, stopFuturesPaperTrading, getFuturesPaperStatus,
  startFuturesSwingTrading, stopFuturesSwingTrading, getFuturesSwingStatus,
  startFuturesSwingPaperTrading, stopFuturesSwingPaperTrading, getFuturesSwingPaperStatus,
  startFuturesAutoRegime, startFuturesPaperRegime, startFuturesSwingRegime, startFuturesSwingPaperRegime,
} from '../services/api'
import CapitalInput from './CapitalInput'
import DailyStrategyStats from './DailyStrategyStats'
import { LOG_COLORS } from '../utils/constants'

const TABS = [
  { id: 'intraday-paper', label: 'Intraday Paper', icon: FlaskConical, color: 'blue' },
  { id: 'intraday-live', label: 'Intraday Live', icon: Zap, color: 'orange' },
  { id: 'swing-paper', label: 'Swing Paper', icon: Activity, color: 'teal' },
  { id: 'swing-live', label: 'Swing Live', icon: Repeat, color: 'emerald' },
]

const TAB_COLORS = {
  blue: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  orange: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  teal: 'bg-teal-500/20 text-teal-400 border border-teal-500/30',
  emerald: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
}

const TAB_CONFIG = {
  'intraday-live': { start: startFuturesAutoTrading, stop: stopFuturesAutoTrading, status: getFuturesAutoStatus, autoStart: startFuturesAutoRegime, isLive: true, isSwing: false },
  'intraday-paper': { start: startFuturesPaperTrading, stop: stopFuturesPaperTrading, status: getFuturesPaperStatus, autoStart: startFuturesPaperRegime, isLive: false, isSwing: false },
  'swing-live': { start: startFuturesSwingTrading, stop: stopFuturesSwingTrading, status: getFuturesSwingStatus, autoStart: startFuturesSwingRegime, isLive: true, isSwing: true },
  'swing-paper': { start: startFuturesSwingPaperTrading, stop: stopFuturesSwingPaperTrading, status: getFuturesSwingPaperStatus, autoStart: startFuturesSwingPaperRegime, isLive: false, isSwing: true },
}

const POLL_INTERVAL = 10_000  // 10s — near real-time

const OI_SENTIMENT_COLORS = {
  long_buildup: 'text-green-400 bg-green-400/10',
  short_covering: 'text-emerald-400 bg-emerald-400/10',
  short_buildup: 'text-red-400 bg-red-400/10',
  long_unwinding: 'text-orange-400 bg-orange-400/10',
}

export default function FuturesPage({ capital, setCapital }) {
  const [activeTab, setActiveTab] = useState('intraday-live')
  const [strategies, setStrategies] = useState([])
  const [selectedStrategies, setSelectedStrategies] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState(null)
  const [autoMode, setAutoMode] = useState(true)
  const [regime, setRegime] = useState(null)
  const pollRef = useRef(null)
  const logEndRef = useRef(null)

  const config = TAB_CONFIG[activeTab]
  const running = status?.is_running ?? false
  const isLive = config.isLive
  const isSwing = config.isSwing

  // Load strategies once
  useEffect(() => {
    getFuturesStrategies().then(data => {
      if (Array.isArray(data)) {
        setStrategies(data)
        const sel = {}
        data.forEach(s => {
          const tfs = s.timeframes || []
          sel[s.id] = { selected: true, timeframe: tfs[0] || '15m' }
        })
        setSelectedStrategies(sel)
      }
    }).catch(() => {})
    // Fetch regime
    getFuturesRegime().then(setRegime).catch(() => {})
  }, [])

  // Poll status
  const pollStatus = useCallback(async () => {
    try {
      const data = await config.status()
      setStatus(data)
    } catch {}
  }, [activeTab])

  useEffect(() => { pollStatus() }, [pollStatus])

  useEffect(() => {
    if (running) {
      pollRef.current = setInterval(pollStatus, POLL_INTERVAL)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [running, pollStatus])

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
        // Auto mode: regime detector picks strategies
        res = await config.autoStart(capital)
        if (res?.regime) setRegime(res.regime)
      } else {
        // Manual mode: user picks strategies
        const strats = Object.entries(selectedStrategies)
          .filter(([, v]) => v.selected)
          .map(([key, v]) => ({ strategy: key, timeframe: v.timeframe }))

        if (strats.length === 0) {
          setError('Select at least one strategy')
          setLoading(false)
          return
        }

        if (isSwing) {
          res = await config.start(strats, capital, 240)
        } else {
          res = await config.start(strats, capital)
        }
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

  const positions = status?.active_trades || []
  const history = status?.trade_history || []
  const logs = status?.logs || []

  return (
    <div className="space-y-5">
      {/* Header + Tab bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 size={22} className="text-amber-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Futures Trading</h2>
            <p className="text-gray-500 text-xs">F&O stock futures with OI sentiment analysis + 4 screener strategies</p>
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
        {!isSwing ? (
          <>
            <span>Start at <span className="text-amber-400 font-semibold">11:50 AM</span></span>
            <span className="text-dark-500">|</span>
            <span>Capital: <span className="text-white">₹1L</span> (paper)</span>
            <span className="text-dark-500">|</span>
            <span>Mode: <span className="text-amber-400">Auto Regime</span> (NIFTY + VIX + OI)</span>
            <span className="text-dark-500">|</span>
            <span>Engine scans at 12:00 PM, auto square-off 3:15 PM</span>
          </>
        ) : (
          <>
            <span>Start at <span className="text-teal-400 font-semibold">11:50 AM</span></span>
            <span className="text-dark-500">|</span>
            <span>Capital: <span className="text-white">₹1L</span> (paper)</span>
            <span className="text-dark-500">|</span>
            <span>Mode: <span className="text-white">Manual</span> (all 4 strategies on 1h/1d)</span>
            <span className="text-dark-500">|</span>
            <span>Scans every 4h, positions carry overnight, rollover before expiry</span>
          </>
        )}
      </div>

      {/* Timing Reference */}
      {!isSwing ? (
        <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-dark-600 text-[10px] text-gray-500">
          <span className="text-amber-400 font-semibold">Intraday</span>
          <span className="text-dark-500">|</span>
          <span>Regime: <span className="text-amber-400">Auto</span> (NIFTY + VIX + ADX + OI → picks strategies)</span>
          <span className="text-dark-500">|</span>
          <span>Scan: <span className="text-amber-400">12:00 PM</span> + on-demand</span>
          <span className="text-dark-500">|</span>
          <span>Orders: <span className="text-amber-400">12:00 PM - 2:00 PM</span></span>
          <span className="text-dark-500">|</span>
          <span>Monitor: <span className="text-white">60s</span> + exchange SL-M</span>
          <span className="text-dark-500">|</span>
          <span>Square-off: <span className="text-red-400">3:15 PM</span> (3 retries)</span>
          <span className="text-dark-500">|</span>
          <span>Positions: <span className="text-white">4 live / 8 paper</span></span>
          <span className="text-dark-500">|</span>
          <span>Risk: <span className="text-white">5%</span> | SL: <span className="text-white">min 1.2%</span></span>
          <span className="text-dark-500">|</span>
          <span>Daily loss: <span className="text-red-400">5% cap</span></span>
          <span className="text-dark-500">|</span>
          <span>Margin ~10% | OI soft filter | Liquidity + brokerage filter</span>
        </div>
      ) : (
        <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-teal-500/10 text-[10px] text-gray-500">
          <span className="text-teal-400 font-semibold">Swing</span>
          <span className="text-dark-500">|</span>
          <span>Regime: <span className="text-amber-400">Auto</span> (refreshes each scan)</span>
          <span className="text-dark-500">|</span>
          <span>Scan: <span className="text-teal-400">every 4 hours</span></span>
          <span className="text-dark-500">|</span>
          <span>Monitor: <span className="text-white">60s</span> + exchange SL-M re-placed daily</span>
          <span className="text-dark-500">|</span>
          <span>Exit: <span className="text-white">SL / Target / Rollover 2d before expiry</span></span>
          <span className="text-dark-500">|</span>
          <span>Positions: <span className="text-white">2 live / 5 paper</span></span>
          <span className="text-dark-500">|</span>
          <span>Risk: <span className="text-white">5%</span> | SL: <span className="text-white">min 1.2%</span></span>
          <span className="text-dark-500">|</span>
          <span>Daily loss: <span className="text-red-400">5% cap</span></span>
          <span className="text-dark-500">|</span>
          <span>Margin ~20% | MARGIN product | OI + liquidity filter</span>
        </div>
      )}

      {/* Market Regime */}
      {regime && (
        <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-gray-400">Market Regime</h3>
            <span className="text-[10px] text-gray-600">NIFTY + VIX + OI Analysis</span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-bold text-amber-400">
              {(regime.regime || regime.components?.nifty_trend?.trend || 'detecting...').replace(/_/g, ' ').toUpperCase()}
            </span>
            {regime.components?.vix > 0 && (
              <span className="text-xs text-gray-500">VIX: {regime.components.vix}</span>
            )}
            {regime.components?.nifty_trend?.adx > 0 && (
              <span className="text-xs text-gray-500">ADX: {regime.components.nifty_trend.adx}</span>
            )}
            {regime.components?.oi_summary?.bullish_pct !== undefined && (
              <span className="text-xs text-gray-500">OI Bullish: {regime.components.oi_summary.bullish_pct}%</span>
            )}
          </div>
          {regime.strategy_ids && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-gray-500">Auto-selected:</span>
              {regime.strategy_ids.map(s => (
                <span key={s} className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  {s.replace('futures_', '').replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Strategy Selection + Capital */}
      {!running && (
        <div className={`bg-dark-700 rounded-xl p-5 border ${isLive ? 'border-orange-500/20' : 'border-blue-500/20'}`}>
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
                <li>Trending market + High VIX → Volume Breakout</li>
                <li>Trending market + Normal VIX → Volume Breakout + EMA Pullback</li>
                <li>Pullback in trend → EMA Pullback + Candlestick Reversal</li>
                <li>Sideways + Low VIX → Mean Reversion</li>
              </ul>
              {regime?.reasoning && (
                <p className="mt-3 text-[10px] text-amber-400/60 border-t border-dark-600 pt-2">
                  Current: {regime.reasoning}
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 mb-4">
            {strategies.map(s => {
              const sel = selectedStrategies[s.id]
              const checked = sel?.selected ?? false
              return (
                <div
                  key={s.id}
                  onClick={() => setSelectedStrategies(prev => ({
                    ...prev,
                    [s.id]: { ...prev[s.id], selected: !checked },
                  }))}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    checked
                      ? isLive
                        ? 'border-orange-500/20 bg-orange-500/5'
                        : 'border-blue-500/20 bg-blue-500/5'
                      : 'border-dark-500 bg-dark-800 hover:border-dark-400'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-semibold ${checked ? (isLive ? 'text-orange-400' : 'text-blue-400') : 'text-gray-400'}`}>
                      {s.name}
                    </span>
                    <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                      checked
                        ? isLive
                          ? 'bg-orange-500 border-orange-500'
                          : 'bg-blue-500 border-blue-500'
                        : 'border-dark-400'
                    }`}>
                      {checked && <span className="text-white text-[10px]">&#10003;</span>}
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-500 line-clamp-2">{s.description}</p>

                  {checked && (
                    <select
                      value={sel?.timeframe || '15m'}
                      onClick={e => e.stopPropagation()}
                      onChange={e => setSelectedStrategies(prev => ({
                        ...prev,
                        [s.id]: { ...prev[s.id], timeframe: e.target.value },
                      }))}
                      className="mt-2 text-xs bg-dark-600 text-gray-300 border border-dark-500 rounded px-2 py-0.5"
                    >
                      {(s.timeframes || []).map(tf => (
                        <option key={tf} value={tf}>{tf}</option>
                      ))}
                    </select>
                  )}
                </div>
              )
            })}
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
                  ? 'bg-gradient-to-r from-orange-500 to-pink-500 text-white hover:shadow-lg hover:shadow-orange-500/25'
                  : 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white hover:shadow-lg hover:shadow-blue-500/25'
              }`}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              Start {isLive ? 'Live' : 'Paper'} {isSwing ? 'Swing' : 'Intraday'} {autoMode ? 'Auto' : ''}
            </button>
            <div className="absolute bottom-full left-0 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 w-72">
              <div className="bg-dark-800 border border-dark-500 rounded-lg p-3 shadow-lg text-[10px] text-gray-400 leading-relaxed">
                {autoMode ? (
                  <>
                    <p className="text-amber-400 font-semibold mb-1">Futures Auto Regime</p>
                    <p>Detects NIFTY trend + VIX + ADX + aggregate OI sentiment. Picks strategies automatically.</p>
                    <p className="mt-1">{isSwing ? 'Scan: every 4h | Exit: rollover 2d before expiry | SL-M re-placed daily' : 'Orders: 12 PM - 2 PM | Square-off: 3:15 PM'} | Risk: 5%/trade | Daily loss: 5% cap</p>
                    <p className="mt-1">OI filter: soft (boosts priority) | Liquidity: min volume 50K | Brokerage-aware</p>
                  </>
                ) : (
                  <>
                    <p className="text-white font-semibold mb-1">Futures Manual Mode</p>
                    <p>You pick strategies and timeframes. OI sentiment + liquidity filters still active.</p>
                    <p className="mt-1">{isSwing ? 'Scan: every 4h | MARGIN product | Exit: rollover 2d before expiry' : 'Orders: 12 PM - 2 PM | INTRADAY product | Square-off: 3:15 PM'}</p>
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
            Stop Trading
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
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: 'Capital', value: status.capital > 0 ? `₹${(status.capital >= 100000 ? (status.capital/100000).toFixed(1)+'L' : (status.capital/1000).toFixed(0)+'K')}` : '--' },
            { label: 'Scans', value: status.scan_count || 0 },
            { label: 'Orders', value: status.order_count || 0 },
            { label: 'P&L', value: `₹${(status.total_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: (status.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400' },
            { label: 'Positions', value: `${positions.length}` },
          ].map(s => (
            <div key={s.label} className="bg-dark-700 rounded-lg p-3 border border-dark-500">
              <div className="text-[10px] text-gray-500 mb-1">{s.label}</div>
              <div className={`text-sm font-bold ${s.color || 'text-white'}`}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Daily Loss Warning */}
      {status?.daily_loss_limit_hit && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-center gap-2">
          <span className="text-red-400 text-xs font-semibold">DAILY LOSS LIMIT HIT</span>
          <span className="text-red-400/70 text-xs">— No new orders today. Daily P&L: ₹{(status.daily_realized_pnl || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
      )}

      {/* Active Positions — hidden for live */}
      {!isLive && positions.length > 0 && (
        <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
          <h3 className="text-xs font-semibold text-gray-400 mb-3">Active Positions</h3>
          <div className="space-y-2">
            {positions.map((t, i) => (
              <div key={i} className="flex items-center justify-between bg-dark-800 rounded-lg px-3 py-2">
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-bold ${t.side === 1 ? 'text-green-400' : 'text-red-400'}`}>
                    {t.signal_type}
                  </span>
                  <span className="text-sm text-white font-semibold">{t.symbol}</span>
                  <span className="text-[10px] text-gray-500">{t.num_lots} lots ({t.quantity} qty)</span>
                  {t.oi_sentiment && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${OI_SENTIMENT_COLORS[t.oi_sentiment] || 'text-gray-400'}`}>
                      {t.oi_sentiment.replace('_', ' ')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-gray-500">Entry ₹{t.entry_price}</span>
                  <span className="text-gray-500">LTP ₹{t.ltp}</span>
                  <span className={t.pnl >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                    ₹{t.pnl?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trade History */}
      {!isLive && (
        <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
          <h3 className="text-xs font-semibold text-gray-400 mb-3">Recent Trades</h3>
          {history.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-4">No completed futures trades yet.</p>
          ) : (
          <div className="space-y-1.5">
            {history.slice(-10).reverse().map((t, i) => (
              <div key={i} className="flex items-center justify-between text-xs bg-dark-800 rounded px-3 py-1.5">
                <div className="flex items-center gap-2">
                  <span className={t.side === 1 ? 'text-green-400' : 'text-red-400'}>{t.signal_type}</span>
                  <span className="text-white">{t.symbol}</span>
                  <span className="text-gray-500">{t.exit_reason}</span>
                </div>
                <span className={t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                  ₹{t.pnl?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
              </div>
            ))}
          </div>
          )}
        </div>
      )}

      {/* Daily Strategy Performance — after trades, before logs */}
      <DailyStrategyStats
        source={isLive ? (isSwing ? 'futures_swing' : 'futures_auto') : (isSwing ? 'futures_swing_paper' : 'futures_paper')}
        days={isSwing ? 14 : 7}
        accent={isLive ? 'orange' : 'blue'}
      />

      {/* Logs */}
      {logs.length > 0 && (
        <div className="bg-dark-700 rounded-xl p-4 border border-dark-500">
          <h3 className="text-xs font-semibold text-gray-400 mb-3">Logs</h3>
          <div className="max-h-60 overflow-y-auto font-mono text-[11px] space-y-0.5">
            {logs.map((log, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gray-600 shrink-0">{log.time?.split('T')[1]?.substring(0, 8) || ''}</span>
                <span style={{ color: LOG_COLORS[log.level] || '#888' }} className="shrink-0 font-semibold w-16">[{log.level}]</span>
                <span className="text-gray-300">{log.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

    </div>
  )
}
