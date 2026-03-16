import React, { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, TrendingDown, ChevronDown, ChevronRight } from 'lucide-react'
import { getTradeHistory } from '../services/api'
import { strategies as strategyList } from '../data/mockData'
import { formatINRCompact } from '../utils/formatters'

const STRAT_MAP = Object.fromEntries(strategyList.map(s => [s.id, s]))

const ACCENT_COLORS = {
  orange: 'text-orange-400',
  blue: 'text-blue-400',
  emerald: 'text-emerald-400',
  violet: 'text-violet-400',
  green: 'text-green-400',
  teal: 'text-teal-400',
}

export default function DailyStrategyStats({ source, days = 7, accent = 'blue' }) {
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedDay, setExpandedDay] = useState(null)

  const accentClass = ACCENT_COLORS[accent] || 'text-blue-400'

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const data = await getTradeHistory(days, source)
        if (!cancelled) setTrades(data.trades || data || [])
      } catch {
        if (!cancelled) setTrades([])
      }
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [source, days])

  if (loading) {
    return (
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
        <p className="text-xs text-gray-500 text-center py-4">Loading strategy history...</p>
      </div>
    )
  }

  if (trades.length === 0) {
    return (
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
        <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <BarChart3 size={16} className={accentClass} />
          Daily Strategy Performance
        </h3>
        <p className="text-xs text-gray-500 text-center py-4">No completed trades in the last {days} days</p>
      </div>
    )
  }

  // Group by date → strategy+timeframe
  const byDate = {}
  for (const t of trades) {
    const date = t.date || (t.closed_at || t.placed_at || '').slice(0, 10)
    if (!date) continue
    if (!byDate[date]) byDate[date] = {}
    const strat = t.strategy || '_unknown'
    const tf = t.timeframe || ''
    const key = `${strat}|${tf}`
    if (!byDate[date][key]) byDate[date][key] = { strategy: strat, timeframe: tf, trades: [] }
    byDate[date][key].trades.push(t)
  }

  const sortedDates = Object.keys(byDate).sort((a, b) => b.localeCompare(a))
  const today = new Date().toISOString().slice(0, 10)
  const activeDay = expandedDay ?? (sortedDates.includes(today) ? today : sortedDates[0])

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
        <BarChart3 size={16} className={accentClass} />
        Daily Strategy Performance
        <span className="text-[10px] text-gray-500 font-normal">Last {days} days</span>
      </h3>

      <div className="space-y-2">
        {sortedDates.map(date => {
          const stratGroups = byDate[date]
          const isExpanded = activeDay === date
          const allTrades = Object.values(stratGroups).flatMap(g => g.trades)
          const dayPnl = allTrades.reduce((s, t) => s + (t.pnl ?? 0), 0)
          const dayWins = allTrades.filter(t => (t.pnl ?? 0) > 0).length
          const dayLosses = allTrades.filter(t => (t.pnl ?? 0) < 0).length
          const dayWinRate = allTrades.length > 0 ? Math.round((dayWins / allTrades.length) * 100) : 0

          const dateLabel = new Date(date + 'T00:00:00').toLocaleDateString('en-IN', {
            weekday: 'short', day: 'numeric', month: 'short'
          })

          return (
            <div key={date} className="border border-dark-500 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpandedDay(isExpanded ? null : date)}
                className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-dark-600/30 transition"
              >
                <div className="flex items-center gap-3">
                  {isExpanded ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-500" />}
                  <span className="text-xs font-semibold text-white">{dateLabel}</span>
                  <span className="text-[10px] text-gray-500">{allTrades.length} trade{allTrades.length !== 1 ? 's' : ''}</span>
                  <span className="text-[10px] text-gray-500">{dayWins}W / {dayLosses}L ({dayWinRate}%)</span>
                </div>
                <span className={`text-xs font-bold tabular-nums ${dayPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {dayPnl >= 0 ? '+' : '-'}{formatINRCompact(dayPnl)}
                </span>
              </button>

              {isExpanded && (
                <div className="px-4 pb-3 space-y-2">
                  {Object.values(stratGroups)
                    .sort((a, b) => {
                      const pnlA = a.trades.reduce((s, t) => s + (t.pnl ?? 0), 0)
                      const pnlB = b.trades.reduce((s, t) => s + (t.pnl ?? 0), 0)
                      return pnlB - pnlA
                    })
                    .map(group => {
                      const strat = STRAT_MAP[group.strategy]
                      const stratLabel = strat ? `${strat.shortName}: ${strat.name}` : group.strategy
                      const pnl = group.trades.reduce((s, t) => s + (t.pnl ?? 0), 0)
                      const wins = group.trades.filter(t => (t.pnl ?? 0) > 0).length
                      const losses = group.trades.filter(t => (t.pnl ?? 0) < 0).length
                      const targets = group.trades.filter(t => t.exit_reason === 'TARGET_HIT').length
                      const sls = group.trades.filter(t => t.exit_reason === 'SL_HIT').length
                      const sqoffs = group.trades.filter(t => t.exit_reason === 'SQUARE_OFF').length

                      return (
                        <div key={`${group.strategy}|${group.timeframe}`}
                          className={`rounded-lg border p-3 ${pnl > 0 ? 'bg-green-500/5 border-green-500/10' : pnl < 0 ? 'bg-red-500/5 border-red-500/10' : 'bg-dark-600 border-dark-500'}`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              {pnl >= 0 ? <TrendingUp size={12} className="text-green-400" /> : <TrendingDown size={12} className="text-red-400" />}
                              <span className="text-[11px] font-semibold text-white">{stratLabel}</span>
                              <span className="text-[9px] text-gray-500 bg-dark-700 px-1.5 py-0.5 rounded">{group.timeframe}</span>
                            </div>
                            <span className={`text-xs font-bold tabular-nums ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pnl >= 0 ? '+' : '-'}{formatINRCompact(pnl)}
                            </span>
                          </div>

                          <div className="flex items-center gap-3 text-[10px] text-gray-500">
                            <span>{group.trades.length} trade{group.trades.length !== 1 ? 's' : ''}</span>
                            <span>{wins}W / {losses}L</span>
                            {targets > 0 && <span className="text-green-400">{targets} target</span>}
                            {sls > 0 && <span className="text-red-400">{sls} SL</span>}
                            {sqoffs > 0 && <span className="text-purple-400">{sqoffs} sq-off</span>}
                          </div>

                          <div className="mt-2 space-y-1">
                            {group.trades.map((t, i) => {
                              const tPnl = t.pnl ?? 0
                              const isBuy = t.signal_type === 'BUY' || t.side === 1
                              const reason = t.exit_reason === 'TARGET_HIT' ? 'TARGET' :
                                t.exit_reason === 'SL_HIT' ? 'SL' :
                                t.exit_reason === 'SQUARE_OFF' ? 'SQ-OFF' : t.exit_reason || ''
                              const reasonColor = t.exit_reason === 'TARGET_HIT' ? 'text-green-400' :
                                t.exit_reason === 'SL_HIT' ? 'text-red-400' : 'text-gray-400'

                              return (
                                <div key={i} className="flex items-center justify-between bg-dark-700/50 rounded px-2 py-1">
                                  <div className="flex items-center gap-2">
                                    <span className={`text-[9px] font-semibold px-1 py-0.5 rounded ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                                      {isBuy ? 'B' : 'S'}
                                    </span>
                                    <span className="text-[11px] text-white font-medium">{t.symbol}</span>
                                    <span className="text-[9px] text-gray-600">qty:{t.quantity}</span>
                                    <span className={`text-[9px] font-semibold ${reasonColor}`}>{reason}</span>
                                  </div>
                                  <span className={`text-[11px] font-semibold tabular-nums ${tPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {tPnl >= 0 ? '+' : '-'}{formatINRCompact(tPnl)}
                                  </span>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )
                    })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
