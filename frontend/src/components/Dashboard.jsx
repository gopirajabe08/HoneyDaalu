import React, { useState, useEffect, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, BarChart3, Activity, Target,
  ShieldAlert, Clock, Trophy,
  RefreshCw, AlertCircle, Wallet, Zap,
} from 'lucide-react'
import {
  getBrokerFunds, getPositions, getOrderbook, getAutoStatus, getPaperStatus,
  getSwingStatus, getSwingPaperStatus,
  getOptionsAutoStatus, getOptionsPaperStatus, getOptionsSwingStatus, getOptionsSwingPaperStatus,
  getFuturesAutoStatus, getFuturesPaperStatus, getFuturesSwingStatus, getFuturesSwingPaperStatus,
  getBTSTStatus, getBTSTPaperStatus,
} from '../services/api'
import DailyStrategyStats from './DailyStrategyStats'

const inr2 = (v) => `${Math.abs(v ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function Dashboard({ brokerStatus }) {
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
  const [btstStatus, setBtstStatus] = useState(null)
  const [btstPaperStatus, setBtstPaperStatus] = useState(null)
  const [brokerage, setBrokerage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      // Fetch all engine statuses in parallel
      const [
        autoRes, paperRes,
        swingRes, swingPaperRes,
        optAutoRes, optPaperRes, optSwingRes, optSwingPaperRes,
        futAutoRes, futPaperRes, futSwingRes, futSwingPaperRes,
        btstRes, btstPaperRes,
      ] = await Promise.all([
        getAutoStatus().catch(() => null),
        getPaperStatus().catch(() => null),
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
        getBTSTStatus().catch(() => null),
        getBTSTPaperStatus().catch(() => null),
      ])

      if (autoRes) setAutoStatus(autoRes)
      if (paperRes) setPaperStatus(paperRes)
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
      if (btstRes) setBtstStatus(btstRes)
      if (btstPaperRes) setBtstPaperStatus(btstPaperRes)

      // Fetch TradeJini data separately (only when connected)
      let fundsRes = null, posRes = null, ordRes = null
      if (brokerStatus?.connected) {
        ;[fundsRes, posRes, ordRes] = await Promise.all([
          getBrokerFunds().catch(() => null),
          getPositions().catch(() => null),
          getOrderbook().catch(() => null),
        ])
      }

      if (fundsRes) setFunds(fundsRes)
      const posArr = posRes?.netPositions || posRes?.data?.netPositions || []
      setPositions(posArr)
      const ordArr = ordRes?.orderBook || ordRes?.data?.orderBook || []
      setOrders(ordArr)
      // Calculate brokerage from actual TradeJini turnover
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
  }, [brokerStatus?.connected])

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

  // ── Positions (from TradeJini — source of truth) ──
  const tradedPositions = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
  const openPositions = tradedPositions.filter(p => (p.netQty || 0) !== 0)
  const closedPositions = tradedPositions.filter(p => (p.netQty || 0) === 0)

  // P&L from TradeJini — use 'pl' field which is total P&L (realized + unrealized) per position
  const totalPnlAllPositions = tradedPositions.reduce((s, p) => s + (p.pl || 0), 0)

  // Win/Loss from TradeJini closed positions
  const winners = closedPositions.filter(p => (p.pl || (p.pl || p.realized_profit || 0) || 0) > 0)
  const losers = closedPositions.filter(p => (p.pl || (p.pl || p.realized_profit || 0) || 0) < 0)
  const winRate = closedPositions.length > 0 ? Math.round((winners.length / closedPositions.length) * 100) : 0
  const avgWin = winners.length > 0 ? winners.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0) / winners.length : 0
  const avgLoss = losers.length > 0 ? Math.abs(losers.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0) / losers.length) : 0
  const avgRR = avgLoss > 0 ? (avgWin / avgLoss).toFixed(1) : '--'

  // Best / Worst from TradeJini closed
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

  // ── Not connected banner (non-blocking) ──
  const showBrokerData = brokerStatus?.connected

  return (
    <div className="space-y-4">
      {/* Error banner */}
      {error && (
        <div className="navi-card flex items-center gap-3" style={{ borderColor: 'var(--negative)', backgroundColor: 'var(--negative-light)' }}>
          <AlertCircle size={16} style={{ color: 'var(--negative)' }} />
          <p className="text-xs" style={{ color: 'var(--negative)' }}>{error}</p>
        </div>
      )}

      {/* Broker not connected */}
      {!showBrokerData && (
        <div className="navi-card flex items-center gap-3" style={{ borderColor: 'var(--warning)', backgroundColor: 'var(--warning-light)' }}>
          <AlertCircle size={16} style={{ color: 'var(--warning)' }} />
          <p className="text-xs" style={{ color: 'var(--warning)' }}>
            TradeJini not connected — connect to see live P&L, positions, and funds.
          </p>
        </div>
      )}

      {/* ── Row 1: Key Stats ── */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Portfolio Value"
          value={availableBalance ? `₹${inr2(availableBalance.total)}` : '--'}
          change={availableBalance ? `Available: ₹${inr2(availableBalance.available)}` : ''}
          icon={<Wallet size={18} />}
          trend="neutral"
        />
        <StatCard
          label="Today's P&L"
          value={showBrokerData ? `${totalPnlAllPositions >= 0 ? '+' : '-'}₹${inr2(totalPnlAllPositions)}` : '--'}
          change={showBrokerData && brokerage > 0 ? `Charges: ₹${inr2(brokerage)}` : ''}
          icon={totalPnlAllPositions >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          trend={totalPnlAllPositions >= 0 ? 'up' : totalPnlAllPositions < 0 ? 'down' : 'neutral'}
        />
        <StatCard
          label="Win Rate"
          value={closedPositions.length > 0 ? `${winRate}%` : '--'}
          change={closedPositions.length > 0 ? `${winners.length}W / ${losers.length}L` : 'No trades yet'}
          icon={<Target size={18} />}
          trend={winRate >= 50 ? 'up' : winRate > 0 ? 'down' : 'neutral'}
        />
        <StatCard
          label="Active Trades"
          value={openPositions.length}
          change={`${closedPositions.length} closed today`}
          icon={<Activity size={18} />}
          trend="neutral"
        />
      </div>

      {/* ── Row 2: Main Content (2-column layout) ── */}
      <div className="grid grid-cols-3 gap-4">
        {/* Left: Engine Status + Positions (2/3 width) */}
        <div className="col-span-2 space-y-4">
          {/* Engine Status Table */}
          <div className="navi-card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Zap size={16} style={{ color: 'var(--accent)' }} />
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Trading Engines</h3>
              </div>
              <button onClick={fetchData} disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] transition-colors"
                style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
            <div className="space-y-1">
              <EngineRow label="Equity Intraday" live={autoStatus} paper={paperStatus} />
              <EngineRow label="Options Intraday" live={optAutoStatus} paper={optPaperStatus} />
              <EngineRow label="BTST" live={btstStatus} paper={btstPaperStatus} />
              <EngineRow label="Equity Swing" live={swingStatus} paper={swingPaperStatus} />
              <EngineRow label="Options Swing" live={optSwingStatus} paper={optSwingPaperStatus} />
              <EngineRow label="Futures Intraday" live={futAutoStatus} paper={futPaperStatus} />
              <EngineRow label="Futures Swing" live={futSwingStatus} paper={futSwingPaperStatus} />
            </div>
          </div>

          {/* Positions Table */}
          {showBrokerData && (
            <div className="navi-card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Activity size={16} style={{ color: 'var(--chart-3)' }} />
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Today's Positions
                  </h3>
                  <span className="badge-accent">{tradedPositions.length} traded</span>
                </div>
                {openPositions.length > 0 && (
                  <span className="badge-positive">{openPositions.length} open</span>
                )}
              </div>

              {tradedPositions.length === 0 ? (
                <div className="text-center py-10">
                  <Activity size={32} className="mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No positions today</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Trades will appear here once engines start scanning</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th className="text-left py-2 font-medium" style={{ color: 'var(--text-muted)' }}>Symbol</th>
                        <th className="text-right py-2 font-medium" style={{ color: 'var(--text-muted)' }}>Qty</th>
                        <th className="text-right py-2 font-medium" style={{ color: 'var(--text-muted)' }}>Buy Avg</th>
                        <th className="text-right py-2 font-medium" style={{ color: 'var(--text-muted)' }}>Sell Avg</th>
                        <th className="text-right py-2 font-medium" style={{ color: 'var(--text-muted)' }}>P&L</th>
                        <th className="text-center py-2 font-medium" style={{ color: 'var(--text-muted)' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tradedPositions.map((p, i) => {
                        const pnl = p.pl || p.realized_profit || 0
                        const isOpen = (p.netQty || 0) !== 0
                        const symbol = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
                        return (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}
                            className="transition-colors"
                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'}
                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          >
                            <td className="py-2.5 font-medium" style={{ color: 'var(--text-primary)' }}>{symbol}</td>
                            <td className="py-2.5 text-right" style={{ color: 'var(--text-secondary)' }}>{Math.abs(p.netQty || p.buyQty || 0)}</td>
                            <td className="py-2.5 text-right" style={{ color: 'var(--text-secondary)' }}>₹{(p.buyAvg || 0).toFixed(2)}</td>
                            <td className="py-2.5 text-right" style={{ color: 'var(--text-secondary)' }}>₹{(p.sellAvg || 0).toFixed(2)}</td>
                            <td className="py-2.5 text-right font-semibold" style={{ color: pnl >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                              {pnl >= 0 ? '+' : ''}₹{pnl.toFixed(2)}
                            </td>
                            <td className="py-2.5 text-center">
                              <span className={isOpen ? 'badge-positive' : 'badge-accent'}>
                                {isOpen ? 'OPEN' : 'CLOSED'}
                              </span>
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
        </div>

        {/* Right: Activity Feed + Trade Highlights (1/3 width) */}
        <div className="space-y-4">
          {/* Trade Highlights */}
          {showBrokerData && closedPositions.length > 0 && (
            <div className="navi-card">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Trophy size={16} style={{ color: 'var(--chart-2)' }} />
                Highlights
              </h3>
              <div className="space-y-3">
                {bestTrade && (
                  <div className="flex items-center justify-between py-2 px-3 rounded-lg" style={{ backgroundColor: 'var(--positive-light)' }}>
                    <div>
                      <p className="text-[10px] font-medium" style={{ color: 'var(--positive)' }}>Best Trade</p>
                      <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {(bestTrade.symbol || '').replace('NSE:', '').replace('-EQ', '')}
                      </p>
                    </div>
                    <span className="text-sm font-bold" style={{ color: 'var(--positive)' }}>
                      +₹{(bestTrade.pl || bestTrade.realized_profit || 0).toFixed(0)}
                    </span>
                  </div>
                )}
                {worstTrade && (
                  <div className="flex items-center justify-between py-2 px-3 rounded-lg" style={{ backgroundColor: 'var(--negative-light)' }}>
                    <div>
                      <p className="text-[10px] font-medium" style={{ color: 'var(--negative)' }}>Worst Trade</p>
                      <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {(worstTrade.symbol || '').replace('NSE:', '').replace('-EQ', '')}
                      </p>
                    </div>
                    <span className="text-sm font-bold" style={{ color: 'var(--negative)' }}>
                      ₹{(worstTrade.pl || worstTrade.realized_profit || 0).toFixed(0)}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between py-2 px-3 rounded-lg" style={{ backgroundColor: 'var(--accent-light)' }}>
                  <div>
                    <p className="text-[10px] font-medium" style={{ color: 'var(--accent)' }}>Avg Risk:Reward</p>
                    <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{avgRR}x</p>
                  </div>
                  <ShieldAlert size={20} style={{ color: 'var(--accent)' }} />
                </div>
              </div>
            </div>
          )}

          {/* Activity Feed */}
          <div className="navi-card">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Clock size={16} style={{ color: 'var(--accent)' }} />
              Recent Activity
            </h3>
            <div className="space-y-0">
              {(() => {
                // Build activity items from engine logs
                const activities = []
                const engines = [
                  { status: autoStatus, name: 'Equity Live', color: 'var(--chart-1)' },
                  { status: paperStatus, name: 'Equity Paper', color: 'var(--chart-2)' },
                  { status: optAutoStatus, name: 'Options Live', color: 'var(--chart-3)' },
                  { status: optPaperStatus, name: 'Options Paper', color: 'var(--chart-4)' },
                  { status: btstStatus, name: 'BTST Live', color: 'var(--warning)' },
                  { status: btstPaperStatus, name: 'BTST Paper', color: 'var(--text-secondary)' },
                ]
                engines.forEach(({ status, name, color }) => {
                  if (!status) return
                  if (status.running) {
                    activities.push({ text: `${name} engine running`, time: status.started_at || '', color, type: 'running' })
                  }
                  const history = status.trade_history || []
                  history.slice(-3).reverse().forEach(t => {
                    const pnl = t.pnl || 0
                    activities.push({
                      text: `${t.symbol || '?'} ${t.exit_reason || 'closed'} ${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(0)}`,
                      time: t.exit_time || t.entry_time || '',
                      color: pnl >= 0 ? 'var(--positive)' : 'var(--negative)',
                      type: 'trade',
                    })
                  })
                })
                if (activities.length === 0) {
                  return (
                    <div className="text-center py-6">
                      <Clock size={24} className="mx-auto mb-2" style={{ color: 'var(--text-muted)' }} />
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No activity yet today</p>
                    </div>
                  )
                }
                return activities.slice(0, 10).map((a, i) => (
                  <div key={i} className="flex items-start gap-3 py-2.5" style={{ borderBottom: i < Math.min(activities.length, 10) - 1 ? '1px solid var(--border)' : 'none' }}>
                    <div className="mt-1 activity-dot flex-shrink-0" style={{ backgroundColor: a.color, color: a.color }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] truncate" style={{ color: 'var(--text-primary)' }}>{a.text}</p>
                      {a.time && (
                        <p className="text-[9px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                          {typeof a.time === 'string' && a.time.includes('T')
                            ? new Date(a.time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
                            : a.time
                          }
                        </p>
                      )}
                    </div>
                  </div>
                ))
              })()}
            </div>
          </div>

          {/* Orders Summary */}
          {showBrokerData && orders.length > 0 && (
            <div className="navi-card">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <BarChart3 size={16} style={{ color: 'var(--chart-1)' }} />
                Orders
              </h3>
              <div className="grid grid-cols-3 gap-2">
                <div className="text-center py-2 rounded-lg" style={{ backgroundColor: 'var(--positive-light)' }}>
                  <p className="text-lg font-bold" style={{ color: 'var(--positive)' }}>{filledOrders.length}</p>
                  <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>Filled</p>
                </div>
                <div className="text-center py-2 rounded-lg" style={{ backgroundColor: 'var(--warning-light)' }}>
                  <p className="text-lg font-bold" style={{ color: 'var(--warning)' }}>{pendingOrders.length}</p>
                  <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>Pending</p>
                </div>
                <div className="text-center py-2 rounded-lg" style={{ backgroundColor: 'var(--negative-light)' }}>
                  <p className="text-lg font-bold" style={{ color: 'var(--negative)' }}>{rejectedOrders.length}</p>
                  <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>Rejected</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Strategy Stats */}
      <DailyStrategyStats />
    </div>
  )
}

// ── Stat Card (top row) ──
function StatCard({ label, value, change, icon, trend }) {
  const trendColor = trend === 'up' ? 'var(--positive)' : trend === 'down' ? 'var(--negative)' : 'var(--accent)'
  return (
    <div className="navi-card navi-card-glow">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: 'var(--accent-light)', color: trendColor }}>
          {icon}
        </div>
      </div>
      <p className="stat-number" style={{ color: 'var(--text-primary)' }}>{value}</p>
      {change && <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>{change}</p>}
    </div>
  )
}

// ── Engine Row (status table) ──
function EngineRow({ label, live, paper }) {
  const liveRunning = live?.running
  const paperRunning = paper?.running
  const livePnl = live?.total_pnl || 0
  const paperPnl = paper?.total_pnl || 0
  const liveScans = live?.scan_count || 0
  const liveTrades = (live?.trade_history || []).length
  const paperTrades = (paper?.trade_history || []).length

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-lg transition-colors"
      style={{ borderBottom: '1px solid var(--border)' }}
      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'}
      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
    >
      <div className="w-28 flex items-center gap-2">
        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: liveRunning ? 'var(--positive)' : paperRunning ? 'var(--warning)' : 'var(--text-muted)' }} />
        <span className="text-[11px] font-medium" style={{ color: 'var(--text-primary)' }}>{label}</span>
      </div>
      <div className="flex-1 flex items-center gap-4 text-[10px]">
        <div className="w-16">
          <span className={liveRunning ? 'badge-positive' : 'badge-accent'} style={!liveRunning && !paperRunning ? { backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-muted)' } : {}}>
            {liveRunning ? 'LIVE' : paperRunning ? 'PAPER' : 'OFF'}
          </span>
        </div>
        <div className="w-20 text-right">
          <span style={{ color: 'var(--text-muted)' }}>Scans: </span>
          <span style={{ color: 'var(--text-secondary)' }}>{liveScans || (paper?.scan_count || 0)}</span>
        </div>
        <div className="w-20 text-right">
          <span style={{ color: 'var(--text-muted)' }}>Trades: </span>
          <span style={{ color: 'var(--text-secondary)' }}>{liveTrades || paperTrades}</span>
        </div>
        <div className="flex-1 text-right">
          <span className="font-semibold" style={{ color: (liveRunning ? livePnl : paperPnl) >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
            {liveRunning ? (livePnl >= 0 ? '+' : '') + '₹' + livePnl.toFixed(0) : paperRunning ? (paperPnl >= 0 ? '+' : '') + '₹' + paperPnl.toFixed(0) : '--'}
          </span>
        </div>
      </div>
    </div>
  )
}
