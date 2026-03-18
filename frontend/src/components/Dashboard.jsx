import React, { useState, useEffect, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, BarChart3, Activity, Target,
  ShieldAlert, Clock, Trophy, ArrowUpRight, ArrowDownRight,
  IndianRupee, RefreshCw, AlertCircle, Wallet, Zap,
} from 'lucide-react'
import {
  getFyersFunds, getPositions, getOrderbook, getAutoStatus, getPaperStatus,
  getStrategyStats, getSwingStatus, getSwingPaperStatus,
  getOptionsAutoStatus, getOptionsPaperStatus, getOptionsSwingStatus, getOptionsSwingPaperStatus,
  getFuturesAutoStatus, getFuturesPaperStatus, getFuturesSwingStatus, getFuturesSwingPaperStatus,
} from '../services/api'
import { formatINRCompact } from '../utils/formatters'
import DailyStrategyStats from './DailyStrategyStats'

const inr2 = (v) => `${Math.abs(v ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function Dashboard({ fyersStatus }) {
  const [funds, setFunds] = useState(null)
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [autoStatus, setAutoStatus] = useState(null)
  const [paperStatus, setPaperStatus] = useState(null)
  const [swingStatus, setSwingStatus] = useState(null)
  const [swingPaperStatus, setSwingPaperStatus] = useState(null)
  const [optAutoStatus, setOptAutoStatus] = useState(null)
  const [optPaperStatus, setOptPaperStatus] = useState(null)
  const [optSwingStatus, setOptSwingStatus] = useState(null)
  const [optSwingPaperStatus, setOptSwingPaperStatus] = useState(null)
  const [futAutoStatus, setFutAutoStatus] = useState(null)
  const [futPaperStatus, setFutPaperStatus] = useState(null)
  const [futSwingStatus, setFutSwingStatus] = useState(null)
  const [futSwingPaperStatus, setFutSwingPaperStatus] = useState(null)
  const [intraStats, setIntraStats] = useState({})
  const [swingStats, setSwingStats] = useState({})
  const [brokerage, setBrokerage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      // Fetch all engine statuses in parallel
      const [
        autoRes, paperRes, intraStatsRes, swingStatsRes,
        swingRes, swingPaperRes,
        optAutoRes, optPaperRes, optSwingRes, optSwingPaperRes,
        futAutoRes, futPaperRes, futSwingRes, futSwingPaperRes,
      ] = await Promise.all([
        getAutoStatus().catch(() => null),
        getPaperStatus().catch(() => null),
        getStrategyStats('auto').catch(() => ({})),
        getStrategyStats('swing').catch(() => ({})),
        getSwingStatus().catch(() => null),
        getSwingPaperStatus().catch(() => null),
        getOptionsAutoStatus().catch(() => null),
        getOptionsPaperStatus().catch(() => null),
        getOptionsSwingStatus().catch(() => null),
        getOptionsSwingPaperStatus().catch(() => null),
        getFuturesAutoStatus().catch(() => null),
        getFuturesPaperStatus().catch(() => null),
        getFuturesSwingStatus().catch(() => null),
        getFuturesSwingPaperStatus().catch(() => null),
      ])

      if (autoRes) setAutoStatus(autoRes)
      if (paperRes) setPaperStatus(paperRes)
      if (intraStatsRes) setIntraStats(intraStatsRes)
      if (swingStatsRes) setSwingStats(swingStatsRes)
      if (swingRes) setSwingStatus(swingRes)
      if (swingPaperRes) setSwingPaperStatus(swingPaperRes)
      if (optAutoRes) setOptAutoStatus(optAutoRes)
      if (optPaperRes) setOptPaperStatus(optPaperRes)
      if (optSwingRes) setOptSwingStatus(optSwingRes)
      if (optSwingPaperRes) setOptSwingPaperStatus(optSwingPaperRes)
      if (futAutoRes) setFutAutoStatus(futAutoRes)
      if (futPaperRes) setFutPaperStatus(futPaperRes)
      if (futSwingRes) setFutSwingStatus(futSwingRes)
      if (futSwingPaperRes) setFutSwingPaperStatus(futSwingPaperRes)

      // Fetch Fyers data separately (only when connected)
      let fundsRes = null, posRes = null, ordRes = null
      if (fyersStatus?.connected) {
        ;[fundsRes, posRes, ordRes] = await Promise.all([
          getFyersFunds().catch(() => null),
          getPositions().catch(() => null),
          getOrderbook().catch(() => null),
        ])
      }

      if (fundsRes) setFunds(fundsRes)
      const posArr = posRes?.netPositions || posRes?.data?.netPositions || []
      setPositions(posArr)
      const ordArr = ordRes?.orderBook || ordRes?.data?.orderBook || []
      setOrders(ordArr)
      // Calculate brokerage from actual Fyers turnover
      const traded = posArr.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
      const totalBuyVal = traded.reduce((s, p) => s + (p.buyVal || 0), 0)
      const totalSellVal = traded.reduce((s, p) => s + (p.sellVal || 0), 0)
      const turnover = totalBuyVal + totalSellVal
      const filledCount = ordArr.filter(o => o.status === 2).length
      const brk = filledCount * 20
      const stt = totalSellVal * 0.00025
      const exch = turnover * 0.0000297
      const gst = (brk + exch) * 0.18
      const sebi = turnover * 0.000001
      const stamp = totalBuyVal * 0.00003
      setBrokerage(Math.round((brk + stt + exch + gst + sebi + stamp) * 100) / 100)
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }, [fyersStatus?.connected])

  useEffect(() => {
    fetchData()
    const iv = setInterval(fetchData, 10000)  // 10s — near real-time
    return () => clearInterval(iv)
  }, [fetchData])

  // ── Funds ──
  const availableBalance = (() => {
    if (!funds?.fund_limit) return null
    const available = funds.fund_limit.find(f => f.title === 'Available Balance')
    const total = funds.fund_limit.find(f => f.title === 'Total Balance')
    return {
      available: available?.equityAmount || 0,
      total: total?.equityAmount || 0,
    }
  })()

  // ── Positions (from Fyers — source of truth) ──
  const tradedPositions = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
  const openPositions = tradedPositions.filter(p => (p.netQty || 0) !== 0)
  const closedPositions = tradedPositions.filter(p => (p.netQty || 0) === 0)

  // P&L from Fyers — use 'pl' field which is total P&L (realized + unrealized) per position
  const totalPnlAllPositions = tradedPositions.reduce((s, p) => s + (p.pl || 0), 0)
  const totalRealizedPnl = closedPositions.reduce((s, p) => s + (p.pl || (p.pl || p.realized_profit || 0) || 0), 0)
  const unrealizedPnl = openPositions.reduce((s, p) => s + (p.pl || p.unrealized_profit || 0), 0)

  // Win/Loss from Fyers closed positions
  const winners = closedPositions.filter(p => (p.pl || (p.pl || p.realized_profit || 0) || 0) > 0)
  const losers = closedPositions.filter(p => (p.pl || (p.pl || p.realized_profit || 0) || 0) < 0)
  const winRate = closedPositions.length > 0 ? Math.round((winners.length / closedPositions.length) * 100) : 0
  const avgWin = winners.length > 0 ? winners.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0) / winners.length : 0
  const avgLoss = losers.length > 0 ? Math.abs(losers.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0) / losers.length) : 0
  const avgRR = avgLoss > 0 ? (avgWin / avgLoss).toFixed(1) : '--'

  // Best / Worst from Fyers closed
  const bestTrade = closedPositions.length > 0
    ? closedPositions.reduce((b, p) => ((p.pl || p.realized_profit || 0) || 0) > (b.realized_profit || 0) ? p : b, closedPositions[0])
    : null
  const worstTrade = closedPositions.length > 0
    ? closedPositions.reduce((w, p) => ((p.pl || p.realized_profit || 0) || 0) < (w.realized_profit || 0) ? p : w, closedPositions[0])
    : null

  // Orders summary
  const filledOrders = orders.filter(o => o.status === 2)
  const rejectedOrders = orders.filter(o => o.status === 5)
  const pendingOrders = orders.filter(o => o.status === 1 || o.status === 6)

  // ── Strategy Performance helpers ──
  const STRAT_NAMES = {
    play1: 'EMA Crossover', play2: 'Triple MA', play3: 'VWAP Pullback',
    play4: 'Supertrend', play5: 'BB Squeeze', play6: 'BB Contra',
    play1_ema_crossover: 'EMA Crossover', play2_triple_ma: 'Triple MA',
    play3_vwap_pullback: 'VWAP Pullback', play4_supertrend: 'Supertrend',
    play5_bb_squeeze: 'BB Squeeze', play6_bb_contra: 'BB Contra',
    bull_call_spread: 'Bull Call', bull_put_spread: 'Bull Put',
    bear_call_spread: 'Bear Call', bear_put_spread: 'Bear Put',
    iron_condor: 'Iron Condor', long_straddle: 'Straddle',
    futures_volume_breakout: 'Fut Volume Breakout',
    futures_candlestick_reversal: 'Fut Reversal',
    futures_mean_reversion: 'Fut Mean Rev',
    futures_ema_rsi_pullback: 'Fut EMA Pullback',
  }

  function rankStrategies(stats) {
    const entries = Object.entries(stats).filter(([, s]) => s.total >= 1)
    if (entries.length === 0) return { best: null, worst: null, active: null }
    const sorted = [...entries].sort((a, b) => b[1].total_pnl - a[1].total_pnl)
    const best = sorted[0][1].total_pnl > 0 ? { id: sorted[0][0], ...sorted[0][1] } : null
    const worst = sorted[sorted.length - 1][1].total_pnl < 0 ? { id: sorted[sorted.length - 1][0], ...sorted[sorted.length - 1][1] } : null
    const bySorted = [...entries].sort((a, b) => b[1].total - a[1].total)
    const active = { id: bySorted[0][0], ...bySorted[0][1] }
    return { best, worst, active }
  }

  const intraRank = rankStrategies(intraStats)
  const swingRank = rankStrategies(swingStats)
  const hasIntraStats = Object.keys(intraStats).some(k => intraStats[k].total > 0)
  const hasSwingStats = Object.keys(swingStats).some(k => swingStats[k].total > 0)

  // ── Not connected banner (non-blocking) ──
  const showFyersData = fyersStatus?.connected

  return (
    <div className="space-y-5">
      {/* Refresh bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">
          Today's Trading
          <span className="text-xs text-gray-500 font-normal ml-2">
            {new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
          </span>
        </h2>
        <button onClick={fetchData} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-dark-700 border border-dark-500 rounded-lg text-gray-400 text-xs hover:text-white transition">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* ── Active Engines Banner ── */}
      <ActiveEngines
        autoStatus={autoStatus} paperStatus={paperStatus}
        swingStatus={swingStatus} swingPaperStatus={swingPaperStatus}
        optAutoStatus={optAutoStatus} optPaperStatus={optPaperStatus}
        optSwingStatus={optSwingStatus} optSwingPaperStatus={optSwingPaperStatus}
        futAutoStatus={futAutoStatus} futPaperStatus={futPaperStatus}
        futSwingStatus={futSwingStatus} futSwingPaperStatus={futSwingPaperStatus}
      />

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-xs text-red-400">{error}</div>
      )}

      {/* Fyers not connected banner */}
      {!showFyersData && (
        <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-3 flex items-center gap-3">
          <AlertCircle size={16} className="text-yellow-400 flex-shrink-0" />
          <p className="text-xs text-yellow-400">Fyers not connected — P&L, positions, and funds will appear after connecting. Engine statuses and strategy performance are available below.</p>
        </div>
      )}

      {/* ── Row 1: Key Metrics (Fyers data) ── */}
      {showFyersData && (
      <div className="grid grid-cols-5 gap-3">
        <MetricCard
          label="Today's P&L (Fyers)"
          value={`${totalPnlAllPositions >= 0 ? '+' : '-'}₹${inr2(totalPnlAllPositions)}`}
          color={totalPnlAllPositions >= 0 ? 'text-green-400' : 'text-red-400'}
          icon={totalPnlAllPositions >= 0 ? TrendingUp : TrendingDown}
          iconColor={totalPnlAllPositions >= 0 ? 'text-green-400' : 'text-red-400'}
          sub={(() => {
            const parts = []
            if (closedPositions.length > 0) parts.push(`Closed: ${totalRealizedPnl >= 0 ? '+' : '-'}₹${inr2(totalRealizedPnl)}`)
            if (openPositions.length > 0) parts.push(`Open: ${unrealizedPnl >= 0 ? '+' : '-'}₹${inr2(unrealizedPnl)}`)
            if (brokerage > 0) parts.push(`Charges: ₹${inr2(brokerage)}`)
            return parts.length > 0 ? parts.join(' · ') : null
          })()}
        />
        <MetricCard
          label="Win Rate"
          value={closedPositions.length > 0 ? `${winRate}%` : '--'}
          color="text-white"
          icon={Target}
          iconColor="text-orange-400"
          sub={closedPositions.length > 0 ? `${winners.length}W / ${losers.length}L of ${closedPositions.length}` : 'No closed trades'}
        />
        <MetricCard
          label="Trades"
          value={tradedPositions.length}
          color="text-white"
          icon={BarChart3}
          iconColor="text-blue-400"
          sub={`${openPositions.length} open · ${closedPositions.length} closed`}
        />
        <MetricCard
          label="Avg R:R"
          value={avgRR}
          color="text-white"
          icon={ShieldAlert}
          iconColor="text-purple-400"
          sub={avgWin > 0 ? `W: ${formatINRCompact(avgWin)} / L: ${formatINRCompact(avgLoss)}` : 'No data'}
        />
        <MetricCard
          label="Available Balance"
          value={availableBalance ? `${formatINRCompact(availableBalance.available)}` : '--'}
          color="text-white"
          icon={Wallet}
          iconColor="text-yellow-400"
          sub={availableBalance ? `Total: ${formatINRCompact(availableBalance.total)}` : 'Loading...'}
        />
      </div>
      )}

      {/* ── Row 2: Positions Table + Trade Highlights (Fyers data) ── */}
      {showFyersData && (
      <div className="grid grid-cols-3 gap-4">
        {/* Positions table — grouped by strategy */}
        <div className="col-span-2 bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity size={16} className="text-blue-400" />
              Today's Positions
              <span className="text-[10px] text-gray-500 font-normal">{tradedPositions.length} stocks traded</span>
            </h3>
            {openPositions.length > 0 && (
              <span className="bg-green-500/15 text-green-400 text-[10px] font-semibold px-2 py-0.5 rounded-full">
                {openPositions.length} open
              </span>
            )}
          </div>

          {tradedPositions.length === 0 ? (
            <div className="text-center py-8">
              <Activity size={28} className="text-gray-600 mx-auto mb-2" />
              <p className="text-gray-500 text-xs">No positions today</p>
            </div>
          ) : (
            <PositionsGroupedByStrategy
              tradedPositions={tradedPositions}
              autoStatus={autoStatus}
              closedPositions={closedPositions}
              totalPnlAllPositions={totalPnlAllPositions}
            />
          )}
        </div>

        {/* Right column: Trade Highlights + Order Summary */}
        <div className="space-y-4">
          {/* Best / Worst Trade */}
          <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Trophy size={16} className="text-yellow-400" />
              Trade Highlights
            </h3>

            {bestTrade ? (
              <div className="space-y-2">
                <HighlightCard
                  label="Best Trade"
                  symbol={(bestTrade.symbol || '').replace('NSE:', '').replace('-EQ', '')}
                  pnl={bestTrade.realized_profit || 0}
                  type={bestTrade.productType}
                  color="green"
                />
                {worstTrade && (worstTrade.realized_profit || 0) < 0 && (
                  <HighlightCard
                    label="Worst Trade"
                    symbol={(worstTrade.symbol || '').replace('NSE:', '').replace('-EQ', '')}
                    pnl={worstTrade.realized_profit || 0}
                    type={worstTrade.productType}
                    color="red"
                  />
                )}
              </div>
            ) : (
              <p className="text-gray-500 text-xs text-center py-4">No closed trades yet</p>
            )}
          </div>

          {/* Order Summary */}
          <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <BarChart3 size={16} className="text-blue-400" />
              Order Summary
            </h3>

            <div className="grid grid-cols-2 gap-2">
              <MiniStat label="Total" value={orders.length} />
              <MiniStat label="Filled" value={filledOrders.length} color="text-green-400" />
              <MiniStat label="Pending" value={pendingOrders.length} color="text-yellow-400" />
              <MiniStat label="Rejected" value={rejectedOrders.length} color={rejectedOrders.length > 0 ? 'text-red-400' : 'text-gray-400'} />
            </div>

            {rejectedOrders.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] text-red-400 font-medium mb-1">Rejected:</p>
                {rejectedOrders.slice(0, 3).map((o, i) => {
                  const sym = (o.symbol || '').replace('NSE:', '').replace('-EQ', '')
                  return (
                    <div key={i} className="text-[10px] text-gray-500 truncate py-0.5">
                      {sym} — {(o.message || '').slice(0, 50)}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* P&L Breakdown */}
          <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <IndianRupee size={16} className="text-yellow-400" />
              P&L Breakdown
            </h3>
            <div className="space-y-2">
              <PnlRow label={`Closed (${closedPositions.length})`} value={totalRealizedPnl} />
              {openPositions.length > 0 && <PnlRow label={`Open (${openPositions.length})`} value={unrealizedPnl} />}
              <div className="border-t border-dark-500 pt-2">
                <PnlRow label="Total P&L (Fyers)" value={totalPnlAllPositions} bold />
              </div>
              {brokerage > 0 && (
                <div className="flex items-center justify-between text-[10px] pt-1">
                  <span className="text-gray-500">Est. Brokerage & Charges</span>
                  <span className="text-red-400/70">₹{inr2(brokerage)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      )}

      {/* ── Row 3: Strategy Performance — All Engines (always visible) ── */}
      <DashboardStrategyPerformance />

      {/* ── Row 4: Per-stock P&L bars (Fyers data) ── */}
      {showFyersData && tradedPositions.length > 0 && (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 size={16} className="text-purple-400" />
            Stock-wise P&L
          </h3>
          <div className="space-y-2">
            {[...tradedPositions]
              .sort((a, b) => (b.pl || 0) - (a.pl || 0))
              .map((p, i) => {
                const sym = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
                const pnl = p.pl || (p.pl || p.realized_profit || 0) || 0
                const maxPnl = Math.max(...tradedPositions.map(x => Math.abs(x.pl || 0)), 1)
                const width = Math.round((Math.abs(pnl) / maxPnl) * 100)

                return (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-xs font-medium text-white w-28 flex-shrink-0">{sym}</span>
                    <div className="flex-1 h-5 bg-dark-600 rounded-full overflow-hidden relative">
                      <div
                        className={`h-full rounded-full transition-all ${pnl >= 0 ? 'bg-green-500/40' : 'bg-red-500/40'}`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className={`text-xs font-bold w-20 text-right flex-shrink-0 ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pnl >= 0 ? '+' : '-'}₹{inr2(pnl)}
                    </span>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ──

function MetricCard({ label, value, color, icon: Icon, iconColor, sub }) {
  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent pointer-events-none" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-gray-500 uppercase font-medium tracking-wide">{label}</span>
          <Icon size={14} className={iconColor} />
        </div>
        <div className={`text-lg font-bold tabular-nums ${color}`}>{value}</div>
        {sub && <p className="text-[10px] text-gray-500 mt-1">{sub}</p>}
      </div>
    </div>
  )
}

function MiniStat({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-dark-600 rounded-lg px-2.5 py-2 text-center">
      <p className={`text-xs font-semibold tabular-nums ${color}`}>{value}</p>
      <p className="text-[9px] text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

function HighlightCard({ label, symbol, pnl, type, color }) {
  const isGreen = color === 'green'
  return (
    <div className={`${isGreen ? 'bg-green-500/5 border-green-500/10' : 'bg-red-500/5 border-red-500/10'} border rounded-xl p-3`}>
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-[10px] ${isGreen ? 'text-green-400' : 'text-red-400'} font-semibold uppercase`}>{label}</p>
          <p className="text-sm font-medium text-white">{symbol}</p>
          <p className="text-[10px] text-gray-500">{type}</p>
        </div>
        <span className={`${isGreen ? 'text-green-400' : 'text-red-400'} font-bold text-sm`}>
          {pnl >= 0 ? '+' : '-'}₹{inr2(pnl)}
        </span>
      </div>
    </div>
  )
}

function StratRankCard({ label, name, stats, color }) {
  const colorMap = {
    green: { bg: 'bg-green-500/5', border: 'border-green-500/10', label: 'text-green-400', icon: TrendingUp },
    red: { bg: 'bg-red-500/5', border: 'border-red-500/10', label: 'text-red-400', icon: TrendingDown },
    blue: { bg: 'bg-blue-500/5', border: 'border-blue-500/10', label: 'text-blue-400', icon: Activity },
  }
  const c = colorMap[color] || colorMap.blue
  const Icon = c.icon
  return (
    <div className={`${c.bg} border ${c.border} rounded-xl p-3`}>
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-[10px] ${c.label} font-semibold uppercase flex items-center gap-1`}>
            <Icon size={10} /> {label}
          </p>
          <p className="text-sm font-medium text-white mt-0.5">{name}</p>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-500">
            <span>{stats.total} trades</span>
            <span>{stats.win_rate}% win</span>
            <span>{stats.wins}W / {stats.losses}L</span>
          </div>
        </div>
        <span className={`font-bold text-sm tabular-nums ${stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {stats.total_pnl >= 0 ? '+' : '-'}{formatINRCompact(stats.total_pnl)}
        </span>
      </div>
    </div>
  )
}

function ActiveEngines({
  autoStatus, paperStatus, swingStatus, swingPaperStatus,
  optAutoStatus, optPaperStatus, optSwingStatus, optSwingPaperStatus,
  futAutoStatus, futPaperStatus, futSwingStatus, futSwingPaperStatus,
}) {
  const colorStyles = {
    orange: { bg: 'bg-orange-500/5 border-orange-500/20', text: 'text-orange-400', dot: 'bg-orange-400' },
    blue: { bg: 'bg-blue-500/5 border-blue-500/20', text: 'text-blue-400', dot: 'bg-blue-400' },
    emerald: { bg: 'bg-emerald-500/5 border-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-400' },
    violet: { bg: 'bg-violet-500/5 border-violet-500/20', text: 'text-violet-400', dot: 'bg-violet-400' },
    purple: { bg: 'bg-purple-500/5 border-purple-500/20', text: 'text-purple-400', dot: 'bg-purple-400' },
    cyan: { bg: 'bg-cyan-500/5 border-cyan-500/20', text: 'text-cyan-400', dot: 'bg-cyan-400' },
    amber: { bg: 'bg-amber-500/5 border-amber-500/20', text: 'text-amber-400', dot: 'bg-amber-400' },
    teal: { bg: 'bg-teal-500/5 border-teal-500/20', text: 'text-teal-400', dot: 'bg-teal-400' },
    pink: { bg: 'bg-pink-500/5 border-pink-500/20', text: 'text-pink-400', dot: 'bg-pink-400' },
    yellow: { bg: 'bg-yellow-500/5 border-yellow-500/20', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  }

  const engines = [
    // Equity
    { key: 'eq-auto', label: 'Equity Intraday Live', status: autoStatus, color: 'orange', icon: Zap },
    { key: 'eq-paper', label: 'Equity Intraday Paper', status: paperStatus, color: 'blue', icon: Target },
    { key: 'eq-swing', label: 'Equity Swing Live', status: swingStatus, color: 'emerald', icon: Activity },
    { key: 'eq-swpaper', label: 'Equity Swing Paper', status: swingPaperStatus, color: 'violet', icon: Target },
    // Options
    { key: 'opt-auto', label: 'Options Intraday Live', status: optAutoStatus, color: 'purple', icon: Zap },
    { key: 'opt-paper', label: 'Options Intraday Paper', status: optPaperStatus, color: 'cyan', icon: Target },
    { key: 'opt-swing', label: 'Options Swing Live', status: optSwingStatus, color: 'pink', icon: Activity },
    { key: 'opt-swpaper', label: 'Options Swing Paper', status: optSwingPaperStatus, color: 'teal', icon: Target },
    // Futures
    { key: 'fut-auto', label: 'Futures Intraday Live', status: futAutoStatus, color: 'amber', icon: Zap },
    { key: 'fut-paper', label: 'Futures Intraday Paper', status: futPaperStatus, color: 'yellow', icon: Target },
    { key: 'fut-swing', label: 'Futures Swing Live', status: futSwingStatus, color: 'emerald', icon: Activity },
    { key: 'fut-swpaper', label: 'Futures Swing Paper', status: futSwingPaperStatus, color: 'teal', icon: Target },
  ]

  const running = engines.filter(e => e.status?.is_running)
  if (running.length === 0) return null

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {running.map(e => {
        const Icon = e.icon
        const cs = colorStyles[e.color]
        const strats = e.status?.strategies?.length || 0
        const trades = e.status?.active_trades?.filter(t => t.status === 'OPEN')?.length
          ?? e.status?.active_positions?.length ?? e.status?.open_positions ?? 0
        const scans = e.status?.total_scans ?? e.status?.scan_count ?? 0
        const pnl = e.status?.total_pnl ?? 0

        return (
          <div key={e.key}
            className={`flex items-center gap-2.5 ${cs.bg} border rounded-xl px-4 py-2.5`}
          >
            <div className="relative flex-shrink-0">
              <Icon size={14} className={cs.text} />
              <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 ${cs.dot} rounded-full animate-pulse`} />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className={`text-xs font-semibold ${cs.text}`}>{e.label}</span>
                <span className="text-[9px] text-gray-500">RUNNING</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-gray-500 mt-0.5">
                {e.status?.capital > 0 && (
                  <>
                    <span className="text-white font-medium">₹{(e.status.capital / 1000).toFixed(0)}K</span>
                    <span>·</span>
                  </>
                )}
                <span>{strats} {strats === 1 ? 'strategy' : 'strategies'}</span>
                <span>·</span>
                <span>{trades} open</span>
                <span>·</span>
                <span>{scans} scans</span>
                {pnl !== 0 && (
                  <>
                    <span>·</span>
                    <span className={pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {pnl >= 0 ? '+' : '-'}{formatINRCompact(pnl)}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function PositionsGroupedByStrategy({ tradedPositions, autoStatus, closedPositions, totalPnlAllPositions }) {
  const STRAT_LABELS = {
    play1_ema_crossover: 'Play #1 — EMA Crossover',
    play2_triple_ma: 'Play #2 — Triple MA',
    play3_vwap_pullback: 'Play #3 — VWAP Pullback',
    play4_supertrend: 'Play #4 — Supertrend',
    play5_bb_squeeze: 'Play #5 — BB Squeeze',
    play6_bb_contra: 'Play #6 — BB Contra',
  }

  // Build symbol → strategy map from auto-trader trades
  const symbolStratMap = {}
  const allTrades = [
    ...(autoStatus?.active_trades || []),
    ...(autoStatus?.trade_history || []),
  ]
  for (const t of allTrades) {
    if (t.symbol && t.strategy) {
      symbolStratMap[t.symbol.toUpperCase()] = t.strategy
    }
  }

  // Group positions by strategy
  const groups = {}
  const sorted = [...tradedPositions].sort((a, b) => Math.abs(b.realized_profit || 0) - Math.abs(a.realized_profit || 0))
  for (const p of sorted) {
    const sym = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
    const strat = symbolStratMap[sym.toUpperCase()] || '_unknown'
    if (!groups[strat]) groups[strat] = []
    groups[strat].push(p)
  }

  // Sort groups: known strategies first (by play order), unknown last
  const groupOrder = Object.keys(groups).sort((a, b) => {
    if (a === '_unknown') return 1
    if (b === '_unknown') return -1
    return a.localeCompare(b)
  })

  const stratColorMap = {
    play1_ema_crossover: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    play2_triple_ma: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    play3_vwap_pullback: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    play4_supertrend: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    play5_bb_squeeze: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
    play6_bb_contra: 'text-teal-400 bg-teal-500/10 border-teal-500/20',
    _unknown: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
  }

  return (
    <div className="overflow-x-auto space-y-4">
      {groupOrder.map(strat => {
        const positionsInGroup = groups[strat]
        const label = STRAT_LABELS[strat] || 'Other / Manual'
        const colors = stratColorMap[strat] || stratColorMap._unknown
        const groupPnl = positionsInGroup.reduce((s, p) => s + (p.pl || (p.pl || p.realized_profit || 0) || 0), 0)
        const groupOpen = positionsInGroup.filter(p => (p.netQty || 0) !== 0).length

        return (
          <div key={strat}>
            <div className={`flex items-center justify-between mb-2 px-1`}>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${colors}`}>
                  {label}
                </span>
                <span className="text-[10px] text-gray-500">
                  {positionsInGroup.length} {positionsInGroup.length === 1 ? 'trade' : 'trades'}
                  {groupOpen > 0 && ` · ${groupOpen} open`}
                </span>
              </div>
              <span className={`text-[11px] font-semibold tabular-nums ${groupPnl > 0 ? 'text-green-400' : groupPnl < 0 ? 'text-red-400' : 'text-gray-500'}`}>
                {groupPnl >= 0 ? '+' : '-'}₹{inr2(groupPnl)}
              </span>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-500">
                  {['Symbol', 'Type', 'Buy Avg', 'Sell Avg', 'Qty', 'Net Qty', 'P&L', 'Status'].map(h => (
                    <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positionsInGroup.map((p, i) => {
                  const sym = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
                  const netQty = p.netQty || 0
                  const pnl = p.pl || (p.pl || p.realized_profit || 0) || 0
                  const isOpen = netQty !== 0
                  const isBuy = (p.buyQty || 0) > 0

                  return (
                    <tr key={i} className="border-b border-dark-600/30 hover:bg-dark-600/20">
                      <td className="px-3 py-2.5">
                        <span className="text-sm font-medium text-white">{sym}</span>
                        <span className="text-[9px] text-gray-600 ml-1.5">{p.productType}</span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'
                        }`}>
                          {isBuy ? <ArrowUpRight size={9} /> : <ArrowDownRight size={9} />}
                          {isBuy ? 'BUY' : 'SELL'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">
                        {p.buyAvg > 0 ? `₹${p.buyAvg.toFixed(1)}` : '--'}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">
                        {p.sellAvg > 0 ? `₹${p.sellAvg.toFixed(1)}` : '--'}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-300">{p.buyQty || p.sellQty}</td>
                      <td className="px-3 py-2.5">
                        {isOpen ? (
                          <span className="text-xs font-semibold text-blue-400">{netQty}</span>
                        ) : (
                          <span className="text-xs text-gray-500">0</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`text-xs font-bold ${pnl > 0 ? 'text-green-400' : pnl < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                          {pnl >= 0 ? '+' : '-'}₹{inr2(pnl)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                          isOpen ? 'bg-blue-500/15 text-blue-400' : pnl > 0 ? 'bg-green-500/15 text-green-400' : pnl < 0 ? 'bg-red-500/15 text-red-400' : 'bg-gray-500/15 text-gray-400'
                        }`}>
                          {isOpen ? 'OPEN' : pnl > 0 ? 'PROFIT' : pnl < 0 ? 'LOSS' : 'FLAT'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )
      })}
      {tradedPositions.length > 0 && (
        <div className="border-t border-dark-400 pt-2 flex items-center justify-between px-3">
          <span className="text-xs font-semibold text-gray-400">Total P&L (Fyers)</span>
          <span className={`text-sm font-bold ${totalPnlAllPositions >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalPnlAllPositions >= 0 ? '+' : '-'}₹{inr2(totalPnlAllPositions)}
          </span>
        </div>
      )}
    </div>
  )
}

function DashboardStrategyPerformance() {
  const [engineTab, setEngineTab] = useState('equity_intraday')
  const [modeTab, setModeTab] = useState('paper')

  const ENGINE_TABS = [
    { id: 'equity_intraday', label: 'Equity Intraday', color: 'orange' },
    { id: 'equity_swing', label: 'Equity Swing', color: 'emerald' },
    { id: 'options_intraday', label: 'Options Intraday', color: 'violet' },
    { id: 'options_swing', label: 'Options Swing', color: 'teal' },
    { id: 'futures_intraday', label: 'Futures Intraday', color: 'amber' },
    { id: 'futures_swing', label: 'Futures Swing', color: 'cyan' },
  ]

  const SOURCE_MAP = {
    equity_intraday: { live: 'auto', paper: 'paper' },
    equity_swing: { live: 'swing', paper: 'swing_paper' },
    options_intraday: { live: 'options_auto', paper: 'options_paper' },
    options_swing: { live: 'options_swing', paper: 'options_swing_paper' },
    futures_intraday: { live: 'futures_auto', paper: 'futures_paper' },
    futures_swing: { live: 'futures_swing', paper: 'futures_swing_paper' },
  }

  const TAB_COLORS = {
    orange: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    emerald: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    violet: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    teal: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    cyan: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  }

  const current = ENGINE_TABS.find(t => t.id === engineTab)
  const source = SOURCE_MAP[engineTab]?.[modeTab] || 'paper'
  const days = engineTab.includes('swing') ? 14 : 7

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <BarChart3 size={16} className="text-purple-400" />
          Strategy Performance
        </h3>

        {/* Live / Paper toggle */}
        <div className="flex items-center gap-1 bg-dark-800 rounded-lg p-0.5 border border-dark-600">
          <button
            onClick={() => setModeTab('live')}
            className={`px-2.5 py-1 rounded-md text-[10px] font-semibold transition-all ${
              modeTab === 'live' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'text-gray-500'
            }`}
          >
            Live
          </button>
          <button
            onClick={() => setModeTab('paper')}
            className={`px-2.5 py-1 rounded-md text-[10px] font-semibold transition-all ${
              modeTab === 'paper' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'text-gray-500'
            }`}
          >
            Paper
          </button>
        </div>
      </div>

      {/* Engine tabs */}
      <div className="flex items-center gap-1 mb-4 bg-dark-800 rounded-xl p-1 border border-dark-600 overflow-x-auto">
        {ENGINE_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setEngineTab(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-[10px] font-semibold whitespace-nowrap transition-all ${
              engineTab === tab.id
                ? TAB_COLORS[tab.color] + ' border'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Strategy stats for selected engine + mode */}
      <DailyStrategyStats source={source} days={days} accent={current?.color || 'blue'} />
    </div>
  )
}

function PnlRow({ label, value, bold }) {
  return (
    <div className="flex items-center justify-between">
      <span className={`text-xs ${bold ? 'text-white font-semibold' : 'text-gray-400'}`}>{label}</span>
      <span className={`text-xs font-semibold tabular-nums ${value >= 0 ? 'text-green-400' : 'text-red-400'} ${bold ? 'text-sm' : ''}`}>
        {value >= 0 ? '+' : '-'}₹{inr2(value)}
      </span>
    </div>
  )
}
