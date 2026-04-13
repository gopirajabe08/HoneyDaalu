import React, { useState, useEffect } from 'react'
import { RefreshCw, TrendingUp, TrendingDown, Calendar, BarChart3, Zap, BookOpen, Wallet, Plus, Minus, X, Settings } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { getDailyPnl, getPositions, getOrderbook, getBrokerFunds, getCapitalInfo, setInitialCapital, addCapitalTransaction, deleteCapitalTransaction } from '../services/api'

const STRATEGY_NAMES = {
  play1: 'EMA Crossover', play1_ema_crossover: 'EMA Crossover',
  play2: 'Triple MA', play2_triple_ma: 'Triple MA',
  play3: 'VWAP Pullback', play3_vwap_pullback: 'VWAP Pullback',
  play4: 'Supertrend', play4_supertrend: 'Supertrend',
  play5: 'BB Squeeze', play5_bb_squeeze: 'BB Squeeze',
  play6: 'BB Contra', play6_bb_contra: 'BB Contra',
  play7_orb: 'ORB Breakout',
  play8_rsi_divergence: 'RSI Divergence',
  play9_gap_analysis: 'Gap Analysis',
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

// Calculate brokerage from actual TradeJini turnover + filled order count
function calcBrokerage(positions, orders) {
  const traded = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
  const totalBuyVal = traded.reduce((s, p) => s + (p.buyVal || 0), 0)
  const totalSellVal = traded.reduce((s, p) => s + (p.sellVal || 0), 0)
  const turnover = totalBuyVal + totalSellVal
  const filledCount = (orders || []).filter(o => o.status === 2).length
  const brokerage = filledCount * 20                    // ₹20 per executed order
  const stt = totalSellVal * 0.00025                    // 0.025% sell side
  const exchange = turnover * 0.0000297                 // ~0.00297%
  const gst = (brokerage + exchange) * 0.18             // 18% on brokerage + exchange
  const sebi = turnover * 0.000001                      // ₹10 per crore
  const stamp = totalBuyVal * 0.00003                   // 0.003% buy side
  return Math.round((brokerage + stt + exchange + gst + sebi + stamp) * 100) / 100
}

export default function DailyPnL() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [days, setDays] = useState(30)
  const [sourceMode, setSourceMode] = useState('live') // 'live' or 'paper'
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [showCapitalPanel, setShowCapitalPanel] = useState(false)
  const [capitalInfo, setCapitalInfo] = useState(null)
  const [capitalInput, setCapitalInput] = useState('')
  const [txnAmount, setTxnAmount] = useState('')
  const [txnNote, setTxnNote] = useState('')

  useEffect(() => { refresh(); refreshCapital() }, [days, sourceMode])

  async function refreshCapital() {
    try {
      const info = await getCapitalInfo(sourceMode === 'live' ? 'live' : 'paper')
      setCapitalInfo(info)
    } catch { setCapitalInfo(null) }
  }

  async function handleSetCapital() {
    const amt = parseFloat(capitalInput)
    if (!amt || amt <= 0) return
    await setInitialCapital(amt, sourceMode === 'live' ? 'live' : 'paper')
    setCapitalInput('')
    refreshCapital()
    refresh()
  }

  async function handleAddFund(type) {
    const amt = parseFloat(txnAmount)
    if (!amt || amt <= 0) return
    await addCapitalTransaction(amt, type, sourceMode === 'live' ? 'live' : 'paper', txnNote)
    setTxnAmount('')
    setTxnNote('')
    refreshCapital()
    refresh()
  }

  async function handleDeleteTxn(idx) {
    await deleteCapitalTransaction(idx, sourceMode === 'live' ? 'live' : 'paper')
    refreshCapital()
    refresh()
  }

  async function refresh() {
    setLoading(true)
    try {
      const apiSource = sourceMode === 'paper' ? 'all_paper' : sourceMode
      const promises = [getDailyPnl(days, apiSource)]
      if (sourceMode === 'live') {
        promises.push(getPositions().catch(() => null))
        promises.push(getOrderbook().catch(() => null))
        promises.push(getBrokerFunds().catch(() => null))
      }
      const [result, posRes, ordRes, fundsRes] = await Promise.all(promises)
      let rows = Array.isArray(result) ? result : []

      // Override today with TradeJini broker data (source of truth for live)
      if (sourceMode === 'live' && posRes) {
        const positions = posRes?.netPositions || posRes?.data?.netPositions || []
        const orders = ordRes?.orderBook || ordRes?.data?.orderBook || []
        const traded = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
        const closed = traded.filter(p => (p.netQty || 0) === 0)
        const fWins = closed.filter(p => (p.pl || p.realized_profit || 0) > 0)
        const fLosers = closed.filter(p => (p.pl || p.realized_profit || 0) < 0)
        const fRealizedPnl = closed.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0)
        const fGrossProfit = fWins.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0)
        const fGrossLoss = fLosers.reduce((s, p) => s + (p.pl || p.realized_profit || 0), 0)
        const fWinRate = (fWins.length + fLosers.length) > 0
          ? Math.round((fWins.length / (fWins.length + fLosers.length)) * 100 * 10) / 10 : 0
        const brokerageToday = calcBrokerage(positions, orders)

        // Extract TradeJini fund data
        const fundList = fundsRes?.fund_limit || []
        const getFundVal = (id) => {
          const f = fundList.find(x => x.id === id)
          return f ? (f.equityAmount || 0) : 0
        }
        const brokerStartOfDay = getFundVal(9)   // "Limit at start of the day"
        const brokerAvailBal = getFundVal(10)     // "Available Balance"
        const brokerTotalBal = getFundVal(1)      // "Total Balance"
        const brokerFundTransfer = getFundVal(6)  // "Fund Transfer" (added today)
        const brokerRealizedPnl = getFundVal(4)   // "Realized Profit and Loss"

        const todayStr = new Date().toLocaleDateString('en-CA')
        const todayIdx = rows.findIndex(d => d.date === todayStr)
        const brokerEntry = {
          date: todayStr,
          total_pnl: Math.round(fRealizedPnl * 100) / 100,
          brokerage: brokerageToday,
          net_pnl: Math.round((fRealizedPnl - brokerageToday) * 100) / 100,
          trades: traded.length,
          wins: fWins.length,
          losses: fLosers.length,
          win_rate: fWinRate,
          gross_profit: Math.round(fGrossProfit * 100) / 100,
          gross_loss: Math.round(fGrossLoss * 100) / 100,
          strategies: todayIdx >= 0 ? rows[todayIdx].strategies : [],
          auto_trades: traded.length,
          paper_trades: 0,
          // Capital from TradeJini
          capital_start: brokerStartOfDay,
          capital_end: brokerAvailBal || brokerTotalBal,
          fund_added: brokerFundTransfer > 0 ? brokerFundTransfer : 0,
          fund_withdrawn: brokerFundTransfer < 0 ? Math.abs(brokerFundTransfer) : 0,
        }
        if (todayIdx >= 0) {
          rows = [...rows]
          rows[todayIdx] = brokerEntry
        } else if (traded.length > 0 || brokerStartOfDay > 0) {
          rows = [...rows, brokerEntry]
        }

        // Recalculate cumulative P&L
        let cumulative = 0
        for (const r of rows) {
          cumulative += r.total_pnl
          r.cumulative_pnl = Math.round(cumulative * 100) / 100
        }

        // Backfill capital for historical rows using TradeJini start-of-day as anchor
        // Today's capital_start = TradeJini "Limit at start of day"
        // Work backwards: previous_day_end = this_day_start
        if (brokerStartOfDay > 0 && rows.length > 0) {
          // Find today's index in sorted rows
          const todayRowIdx = rows.findIndex(r => r.date === todayStr)
          if (todayRowIdx >= 0) {
            // Backward pass: each prior day's capital_end = next day's capital_start
            let nextStart = brokerStartOfDay
            for (let i = todayRowIdx - 1; i >= 0; i--) {
              const row = rows[i]
              row.capital_end = Math.round(nextStart * 100) / 100
              const rowNetPnl = row.net_pnl ?? row.total_pnl
              const rowFundNet = (row.fund_added || 0) - (row.fund_withdrawn || 0)
              row.capital_start = Math.round((row.capital_end - rowNetPnl - rowFundNet) * 100) / 100
              nextStart = row.capital_start
            }
          }
        }
      }

      setData(rows)
    } catch {
      setData([])
    }
    setLoading(false)
  }

  const isLive = sourceMode === 'live'
  const accentActive = isLive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'

  // Summary stats (use gross total_pnl — brokerage shown separately)
  const totalPnl = data.reduce((s, d) => s + d.total_pnl, 0)
  const totalBrokerage = data.reduce((s, d) => s + (d.brokerage || 0), 0)
  const totalTrades = data.reduce((s, d) => s + d.trades, 0)
  const greenDays = data.filter(d => d.total_pnl > 0).length
  const redDays = data.filter(d => d.total_pnl < 0).length
  const flatDays = data.filter(d => d.total_pnl === 0).length
  const bestDay = data.length > 0 ? data.reduce((best, d) => d.total_pnl > best.total_pnl ? d : best, data[0]) : null
  const worstDay = data.length > 0 ? data.reduce((worst, d) => d.total_pnl < worst.total_pnl ? d : worst, data[0]) : null
  const avgDailyPnl = data.length > 0 ? totalPnl / data.length : 0
  const maxDrawdown = (() => {
    let peak = 0, dd = 0
    for (const d of data) {
      if (d.cumulative_pnl > peak) peak = d.cumulative_pnl
      const cur = peak - d.cumulative_pnl
      if (cur > dd) dd = cur
    }
    return dd
  })()


  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <BarChart3 size={18} className={isLive ? 'text-emerald-400' : 'text-blue-400'} />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Daily P&L</h2>
          {/* Live / Paper toggle */}
          <div className="flex items-center bg-dark-700 rounded-xl border border-dark-500 p-0.5">
            <button
              onClick={() => setSourceMode('live')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isLive ? 'bg-emerald-500/15 text-emerald-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <Zap size={12} /> Live
            </button>
            <button
              onClick={() => setSourceMode('paper')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                !isLive ? 'bg-blue-500/15 text-blue-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <BookOpen size={12} /> Paper
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Days filter */}
          <div className="flex items-center gap-1.5 bg-dark-700 rounded-lg border border-dark-500 px-2 py-1">
            <Calendar size={12} className="text-gray-500" />
            {[1, 7, 14, 30, 90].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
                  days === d ? accentActive : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {d === 1 ? 'Today' : `${d}d`}
              </button>
            ))}
          </div>
          <button onClick={() => setShowCapitalPanel(!showCapitalPanel)} className={`transition-colors ${showCapitalPanel ? 'text-violet-400' : 'text-gray-500 hover:text-gray-300'}`} title="Capital Settings">
            <Wallet size={16} />
          </button>
          <button onClick={refresh} disabled={loading} className="text-gray-500 hover:text-gray-300 transition-colors">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Capital Settings Panel */}
      {showCapitalPanel && (
        <div className="bg-dark-700 rounded-2xl border border-violet-500/30 p-4 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <Wallet size={14} className="text-violet-400" />
            <h3 className="text-xs font-semibold text-violet-400">Capital Settings</h3>
            <span className="text-[10px] text-gray-500 ml-1">({sourceMode === 'live' ? 'Live' : 'Paper'})</span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Set Initial Capital */}
            <div>
              <p className="text-[10px] text-gray-500 mb-1.5">Initial Capital</p>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={capitalInput}
                  onChange={e => setCapitalInput(e.target.value)}
                  placeholder={capitalInfo?.initial_capital ? `Current: ₹${capitalInfo.initial_capital.toLocaleString('en-IN')}` : 'e.g. 100000'}
                  className="flex-1 bg-dark-800 border border-dark-500 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:border-violet-500/50 outline-none"
                />
                <button
                  onClick={handleSetCapital}
                  className="px-3 py-1.5 bg-violet-500/20 text-violet-400 rounded-lg text-xs font-medium hover:bg-violet-500/30 transition-colors"
                >
                  Set
                </button>
              </div>
              {capitalInfo?.initial_capital > 0 && (
                <p className="text-[10px] text-green-400/70 mt-1">Current: {'\u20B9'}{capitalInfo.initial_capital.toLocaleString('en-IN')}</p>
              )}
            </div>

            {/* Add / Withdraw Funds */}
            <div>
              <p className="text-[10px] text-gray-500 mb-1.5">Add / Withdraw Funds</p>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={txnAmount}
                  onChange={e => setTxnAmount(e.target.value)}
                  placeholder="Amount"
                  className="w-28 bg-dark-800 border border-dark-500 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:border-violet-500/50 outline-none"
                />
                <input
                  type="text"
                  value={txnNote}
                  onChange={e => setTxnNote(e.target.value)}
                  placeholder="Note (optional)"
                  className="flex-1 bg-dark-800 border border-dark-500 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:border-violet-500/50 outline-none"
                />
                <button
                  onClick={() => handleAddFund('add')}
                  className="px-2 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-xs font-medium hover:bg-green-500/30 transition-colors"
                  title="Add Funds"
                >
                  <Plus size={14} />
                </button>
                <button
                  onClick={() => handleAddFund('withdraw')}
                  className="px-2 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-colors"
                  title="Withdraw Funds"
                >
                  <Minus size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Transaction History */}
          {capitalInfo?.transactions?.length > 0 && (
            <div className="mt-3 border-t border-dark-500 pt-2">
              <p className="text-[10px] text-gray-500 mb-1.5">Fund Transactions</p>
              <div className="space-y-1 max-h-24 overflow-y-auto">
                {capitalInfo.transactions.map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-[10px] bg-dark-800/50 rounded px-2 py-1">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">{t.date}</span>
                      <span className={t.type === 'add' ? 'text-green-400' : 'text-red-400'}>
                        {t.type === 'add' ? '+' : '-'}{'\u20B9'}{t.amount.toLocaleString('en-IN')}
                      </span>
                      {t.note && <span className="text-gray-600">{t.note}</span>}
                    </div>
                    <button onClick={() => handleDeleteTxn(i)} className="text-gray-600 hover:text-red-400 transition-colors">
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Summary Cards */}
      <div className={`grid ${isLive ? 'grid-cols-3 sm:grid-cols-7' : 'grid-cols-3 sm:grid-cols-6'} gap-3 mb-4`}>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Gross P&L</p>
          <p className={`text-lg font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{totalPnl.toFixed(0)}
          </p>
        </div>
        {isLive && (
          <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
            <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Charges</p>
            <p className="text-lg font-bold text-red-400/80">
              -{'\u20B9'}{totalBrokerage.toFixed(0)}
            </p>
          </div>
        )}
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Net P&L</p>
          <p className={`text-lg font-bold ${(totalPnl - totalBrokerage) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(totalPnl - totalBrokerage) >= 0 ? '+' : ''}{'\u20B9'}{(totalPnl - totalBrokerage).toFixed(0)}
          </p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Green / Red Days</p>
          <p className="text-lg font-bold">
            <span className="text-green-400">{greenDays}</span>
            <span className="text-gray-600 mx-1">/</span>
            <span className="text-red-400">{redDays}</span>
            {flatDays > 0 && <span className="text-gray-500 text-xs ml-1">({flatDays} flat)</span>}
          </p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Total Trades</p>
          <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{totalTrades}</p>
        </div>
        <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>{isLive ? 'Avg Daily P&L' : 'Max Drawdown'}</p>
          <p className={`text-lg font-bold ${isLive ? (avgDailyPnl >= 0 ? 'text-green-400' : 'text-red-400') : 'text-red-400/80'}`}>
            {isLive ? `${avgDailyPnl >= 0 ? '+' : ''}\u20B9${avgDailyPnl.toFixed(0)}` : `\u20B9${maxDrawdown.toFixed(0)}`}
          </p>
        </div>
      </div>

      {/* Charts */}
      {data.length === 0 ? (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5 mb-4">
          <p className="text-xs text-gray-600 text-center py-12">
            No {isLive ? 'live' : 'paper'} trade data in the last {days} days.
          </p>
        </div>
      ) : (() => {
        const totalProfit = data.filter(d => d.total_pnl > 0).reduce((s, d) => s + d.total_pnl, 0)
        const totalLoss = Math.abs(data.filter(d => d.total_pnl < 0).reduce((s, d) => s + d.total_pnl, 0))
        const pieData = [
          { name: 'Profit', value: Math.round(totalProfit), color: '#22c55e' },
          { name: 'Loss', value: Math.round(totalLoss), color: '#ef4444' },
        ].filter(d => d.value > 0)

        // Strategy-wise P&L pie
        const stratPnl = {}
        data.forEach(d => {
          (d.strategies || []).forEach(s => {
            stratPnl[s] = (stratPnl[s] || 0) + d.total_pnl
          })
        })
        const stratColors = ['#10b981', '#3b82f6', '#a855f7', '#eab308', '#06b6d4', '#ec4899']
        const stratPieData = Object.entries(stratPnl)
          .map(([key, val], i) => ({ name: STRATEGY_NAMES[key] || key, value: Math.round(Math.abs(val)), pnl: Math.round(val), color: stratColors[i % stratColors.length] }))
          .filter(d => d.value > 0)
          .sort((a, b) => b.value - a.value)

        const PieTooltip = ({ active, payload }) => {
          if (!active || !payload?.length) return null
          const d = payload[0]?.payload
          if (!d) return null
          return (
            <div className="bg-dark-800 border border-dark-500 rounded-xl p-3 shadow-xl text-xs">
              <p className="font-medium" style={{ color: d.color }}>{d.name}</p>
              <p className="text-white font-bold mt-1">{'\u20B9'}{d.value.toLocaleString('en-IN')}</p>
              {d.pnl !== undefined && (
                <p className={`text-[10px] mt-0.5 ${d.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {d.pnl >= 0 ? '+' : ''}{'\u20B9'}{d.pnl.toLocaleString('en-IN')}
                </p>
              )}
            </div>
          )
        }

        const renderLabel = ({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`

        return (
          <div className={`grid ${isLive && totalBrokerage > 0 ? 'grid-cols-3' : 'grid-cols-2'} gap-4 mb-4`}>
            {/* Profit vs Loss Pie */}
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-xs font-semibold text-gray-400 mb-3">Profit vs Loss</h3>
              {pieData.length === 0 ? (
                <p className="text-xs text-gray-600 text-center py-16">No profit or loss data</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={3}
                      dataKey="value"
                      label={renderLabel}
                      isAnimationActive={false}
                    >
                      {pieData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.color} fillOpacity={0.85} stroke={entry.color} strokeWidth={1} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              )}
              {/* Legend */}
              <div className="flex items-center justify-center gap-6 mt-2">
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
                  <span className="text-[10px] text-gray-400">Profit {'\u20B9'}{Math.round(totalProfit).toLocaleString('en-IN')}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                  <span className="text-[10px] text-gray-400">Loss {'\u20B9'}{Math.round(totalLoss).toLocaleString('en-IN')}</span>
                </div>
              </div>
            </div>

            {/* Strategy-wise P&L Pie */}
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
              <h3 className="text-xs font-semibold text-gray-400 mb-3">Strategy-wise P&L</h3>
              {stratPieData.length === 0 ? (
                <p className="text-xs text-gray-600 text-center py-16">No strategy data</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={stratPieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={3}
                      dataKey="value"
                      label={({ name, percent }) => `${name.split(' ')[0]} ${(percent * 100).toFixed(0)}%`}
                      isAnimationActive={false}
                    >
                      {stratPieData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.color} fillOpacity={0.85} stroke={entry.color} strokeWidth={1} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              )}
              {/* Legend */}
              <div className="flex flex-wrap items-center justify-center gap-3 mt-2">
                {stratPieData.map((s, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                    <span className={`text-[10px] ${s.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {s.name} {s.pnl >= 0 ? '+' : ''}{'\u20B9'}{s.pnl.toLocaleString('en-IN')}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Brokerage Pie (Live mode only) */}
            {isLive && totalBrokerage > 0 && (() => {
              const brkDays = data.filter(d => (d.brokerage || 0) > 0)
              const brkPieData = brkDays.map(d => ({
                name: d.date.substring(5),
                value: Math.round(d.brokerage),
                date: d.date,
                trades: d.trades,
                color: '#ef4444',
              }))
              return (
                <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
                  <h3 className="text-xs font-semibold text-gray-400 mb-3">
                    Brokerage & Charges
                    <span className="text-red-400/70 ml-2 font-bold">{'\u20B9'}{totalBrokerage.toFixed(0)}</span>
                  </h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={brkDays.map(d => ({ ...d, label: d.date.substring(5) }))} barCategoryGap="20%">
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#6b7280' }} />
                      <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `₹${v}`} />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null
                          const d = payload[0]?.payload
                          if (!d || !d.brokerage) return null
                          return (
                            <div className="bg-dark-800 border border-dark-500 rounded-xl p-3 shadow-xl text-xs">
                              <p className="text-gray-400 font-medium mb-1">{d.date}</p>
                              <p className="text-red-400 font-bold">{'\u20B9'}{d.brokerage.toFixed(2)}</p>
                              <p className="text-gray-500 mt-1">{d.trades} trades</p>
                            </div>
                          )
                        }}
                      />
                      <Bar dataKey="brokerage" radius={[4, 4, 0, 0]} fill="#ef4444" fillOpacity={0.4} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )
            })()}
          </div>
        )
      })()}

      {/* Best / Worst Day — only show if distinct and relevant */}
      {data.length > 1 && (bestDay?.total_pnl > 0 || (worstDay?.total_pnl < 0)) && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          {bestDay && bestDay.total_pnl > 0 && bestDay.date !== worstDay?.date && (
            <div className="bg-dark-700 rounded-xl border border-dark-500 p-3 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-green-500/15 flex items-center justify-center">
                <TrendingUp size={16} className="text-green-400" />
              </div>
              <div>
                <p className="text-[10px] text-gray-500">Best Day</p>
                <p className="text-sm font-bold text-green-400">+{'\u20B9'}{bestDay.total_pnl.toFixed(0)}</p>
                <p className="text-[10px] text-gray-500">{bestDay.date} &middot; {bestDay.trades} trades</p>
              </div>
            </div>
          )}
          {worstDay && worstDay.total_pnl < 0 && worstDay.date !== bestDay?.date && (
            <div className="bg-dark-700 rounded-xl border border-dark-500 p-3 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-red-500/15 flex items-center justify-center">
                <TrendingDown size={16} className="text-red-400" />
              </div>
              <div>
                <p className="text-[10px] text-gray-500">Worst Day</p>
                <p className="text-sm font-bold text-red-400">{'\u20B9'}{worstDay.total_pnl.toFixed(0)}</p>
                <p className="text-[10px] text-gray-500">{worstDay.date} &middot; {worstDay.trades} trades</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Daily Breakdown Table */}
      {(() => {
        const todayStr = new Date().toLocaleDateString('en-CA')
        const filtered = data.filter(d => {
          if (dateFrom && d.date < dateFrom) return false
          if (dateTo && d.date > dateTo) return false
          return true
        })
        const totGross = filtered.reduce((s, d) => s + d.total_pnl, 0)
        const totCharges = filtered.reduce((s, d) => s + (d.brokerage || 0), 0)
        const totNet = filtered.reduce((s, d) => s + (d.net_pnl ?? d.total_pnl), 0)
        const totFundAdded = filtered.reduce((s, d) => s + (d.fund_added || 0), 0)
        const totFundWithdrawn = filtered.reduce((s, d) => s + (d.fund_withdrawn || 0), 0)
        const totFundNet = totFundAdded - totFundWithdrawn
        const totTrades = filtered.reduce((s, d) => s + d.trades, 0)
        const totWins = filtered.reduce((s, d) => s + d.wins, 0)
        const totLosses = filtered.reduce((s, d) => s + d.losses, 0)
        const totWinRate = (totWins + totLosses) > 0 ? Math.round((totWins / (totWins + totLosses)) * 1000) / 10 : 0

        return (
          <div className="rounded-2xl border p-5" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Daily Breakdown</h3>
                {isLive && (
                  <span className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    TradeJini = Source of Truth (today)
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={dateFrom}
                  onChange={e => setDateFrom(e.target.value)}
                  className="bg-dark-800 border border-dark-500 rounded-lg px-2 py-1 text-[10px] text-gray-300 outline-none focus:border-violet-500/50"
                />
                <span className="text-gray-600 text-[10px]">to</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={e => setDateTo(e.target.value)}
                  className="bg-dark-800 border border-dark-500 rounded-lg px-2 py-1 text-[10px] text-gray-300 outline-none focus:border-violet-500/50"
                />
                {(dateFrom || dateTo) && (
                  <button onClick={() => { setDateFrom(''); setDateTo('') }} className="text-gray-500 hover:text-gray-300 text-[10px]">
                    Clear
                  </button>
                )}
              </div>
            </div>
            {filtered.length === 0 ? (
              <p className="text-xs text-gray-600 text-center py-8">No {isLive ? 'live' : 'paper'} trade data{dateFrom || dateTo ? ' in selected range' : ' yet'}.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr style={{ borderBottomWidth: '1px', borderColor: 'var(--border)' }}>
                      <th className="text-left text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Date</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Source</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Capital Start</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Gross P&L</th>
                      {isLive && <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Charges</th>}
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Net P&L</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Fund +/-</th>
                      <th className="text-right text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Capital End</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Trades</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>W / L</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Win %</th>
                      <th className="text-center text-[10px] font-medium pb-2" style={{ color: 'var(--text-secondary)' }}>Strategies</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...filtered].reverse().map((d, i) => {
                      const hasCapital = d.capital_start > 0
                      const fundNet = (d.fund_added || 0) - (d.fund_withdrawn || 0)
                      const netPnl = d.net_pnl ?? d.total_pnl
                      const isTradeJiniDay = isLive && d.date === todayStr && d.auto_trades > 0
                      return (
                        <tr key={i} className={`border-b border-dark-600/50 hover:bg-dark-600/30 ${isTradeJiniDay ? 'bg-emerald-500/5' : ''}`}>
                          <td className="py-2 text-xs" style={{ color: 'var(--text-primary)' }}>{d.date}</td>
                          <td className="py-2 text-center">
                            {isTradeJiniDay ? (
                              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                BROKER
                              </span>
                            ) : (
                              <span className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-gray-500/10 text-gray-500">
                                ENGINE
                              </span>
                            )}
                          </td>
                          <td className="py-2 text-right text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {hasCapital ? `\u20B9${d.capital_start.toLocaleString('en-IN')}` : '--'}
                          </td>
                          <td className={`py-2 text-right text-xs font-semibold ${d.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {d.total_pnl >= 0 ? '+' : ''}{'\u20B9'}{d.total_pnl.toFixed(0)}
                          </td>
                          {isLive && (
                            <td className="py-2 text-right text-xs text-red-400/50">
                              {d.brokerage > 0 ? `\u20B9${d.brokerage.toFixed(0)}` : '--'}
                            </td>
                          )}
                          <td className={`py-2 text-right text-xs font-semibold ${netPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {netPnl >= 0 ? '+' : ''}{'\u20B9'}{netPnl.toFixed(0)}
                          </td>
                          <td className="py-2 text-right text-xs">
                            {fundNet !== 0 ? (
                              <span className={fundNet > 0 ? 'text-blue-400' : 'text-emerald-400'}>
                                {fundNet > 0 ? '+' : ''}{'\u20B9'}{fundNet.toLocaleString('en-IN')}
                              </span>
                            ) : <span className="text-gray-600">--</span>}
                          </td>
                          <td className={`py-2 text-right text-xs font-medium ${hasCapital && d.capital_end >= d.capital_start ? 'text-green-400/80' : hasCapital ? 'text-red-400/80' : ''}`} style={{ color: !hasCapital ? 'var(--text-secondary)' : undefined }}>
                            {hasCapital ? `\u20B9${d.capital_end.toLocaleString('en-IN')}` : '--'}
                          </td>
                          <td className="py-2 text-center text-xs" style={{ color: 'var(--text-primary)' }}>{d.trades}</td>
                          <td className="py-2 text-center text-xs">
                            <span className="text-green-400">{d.wins}</span>
                            <span className="text-gray-600 mx-0.5">/</span>
                            <span className="text-red-400">{d.losses}</span>
                          </td>
                          <td className="py-2 text-center text-xs" style={{ color: 'var(--text-primary)' }}>{d.win_rate}%</td>
                          <td className="py-2 text-center">
                            <div className="flex flex-wrap gap-1 justify-center">
                              {(d.strategies || []).map(s => (
                                <span key={s} className="text-[9px] text-gray-400 bg-dark-600 px-1.5 py-0.5 rounded">
                                  {STRATEGY_NAMES[s] || s}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                  {/* Totals Row */}
                  <tfoot>
                    <tr className="border-t-2 border-dark-400 bg-dark-800/50">
                      <td className="py-2.5 text-xs font-bold" style={{ color: 'var(--text-primary)' }}>Total ({filtered.length} days)</td>
                      <td className="py-2.5"></td>
                      <td className="py-2.5 text-right text-xs text-gray-500">--</td>
                      <td className={`py-2.5 text-right text-xs font-bold ${totGross >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {totGross >= 0 ? '+' : ''}{'\u20B9'}{Math.round(totGross).toLocaleString('en-IN')}
                      </td>
                      {isLive && (
                        <td className="py-2.5 text-right text-xs font-bold text-red-400/70">
                          -{'\u20B9'}{Math.round(totCharges).toLocaleString('en-IN')}
                        </td>
                      )}
                      <td className={`py-2.5 text-right text-xs font-bold ${totNet >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {totNet >= 0 ? '+' : ''}{'\u20B9'}{Math.round(totNet).toLocaleString('en-IN')}
                      </td>
                      <td className="py-2.5 text-right text-xs font-bold">
                        {totFundNet !== 0 ? (
                          <span className={totFundNet > 0 ? 'text-blue-400' : 'text-emerald-400'}>
                            {totFundNet > 0 ? '+' : ''}{'\u20B9'}{Math.round(totFundNet).toLocaleString('en-IN')}
                          </span>
                        ) : <span className="text-gray-600">--</span>}
                      </td>
                      <td className="py-2.5 text-right text-xs text-gray-500">--</td>
                      <td className="py-2.5 text-center text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{totTrades}</td>
                      <td className="py-2.5 text-center text-xs font-bold">
                        <span className="text-green-400">{totWins}</span>
                        <span className="text-gray-600 mx-0.5">/</span>
                        <span className="text-red-400">{totLosses}</span>
                      </td>
                      <td className="py-2.5 text-center text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{totWinRate}%</td>
                      <td className="py-2.5"></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        )
      })()}
    </div>
  )
}
