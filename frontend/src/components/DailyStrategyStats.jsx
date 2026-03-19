import React, { useState, useEffect } from 'react'
import { BarChart3, ChevronDown, ChevronRight } from 'lucide-react'
import { getTradeHistory } from '../services/api'
import { strategies as strategyList } from '../data/mockData'
import { formatINRCompact } from '../utils/formatters'

const STRAT_MAP = Object.fromEntries(strategyList.map(s => [s.id, s]))

const EXTRA_STRAT_NAMES = {
  bull_call_spread: 'Bull Call', bull_put_spread: 'Bull Put',
  bear_call_spread: 'Bear Call', bear_put_spread: 'Bear Put',
  iron_condor: 'Iron Condor', long_straddle: 'Straddle',
  futures_volume_breakout: 'Vol Breakout',
  futures_candlestick_reversal: 'Reversal',
  futures_mean_reversion: 'Mean Rev',
  futures_ema_rsi_pullback: 'EMA Pullback',
  play7_orb: 'ORB Breakout',
  play8_rsi_divergence: 'RSI Divergence',
  play9_gap_analysis: 'Gap Analysis',
}

const STRAT_COLORS = [
  '#f97316', '#3b82f6', '#10b981', '#a855f7', '#ec4899', '#06b6d4',
  '#eab308', '#ef4444', '#6366f1', '#14b8a6', '#f43f5e', '#8b5cf6',
]

const ACCENT_COLORS = {
  orange: 'text-orange-400', blue: 'text-blue-400', emerald: 'text-emerald-400',
  violet: 'text-violet-400', green: 'text-green-400', teal: 'text-teal-400',
}

// SVG Donut with hover tooltip
function Donut({ segments, size = 85, strokeWidth = 10, centerLabel, centerValue, centerColor, tooltipData }) {
  const [hovered, setHovered] = useState(null)
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const cx = size / 2
  const cy = size / 2
  let offset = 0

  return (
    <div className="relative group" onMouseLeave={() => setHovered(null)}>
      <svg width={size} height={size} className="-rotate-90">
        {segments.length === 0 && (
          <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#1a1a2e" strokeWidth={strokeWidth} />
        )}
        {segments.map((seg, i) => {
          const dash = (seg.pct / 100) * circumference
          const gap = circumference - dash
          const el = (
            <circle
              key={i}
              cx={cx} cy={cy} r={radius}
              fill="none"
              stroke={hovered === i ? seg.hoverColor || seg.color : seg.color}
              strokeWidth={hovered === i ? strokeWidth + 3 : strokeWidth}
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={-offset}
              strokeLinecap="round"
              className="transition-all duration-150 cursor-pointer"
              onMouseEnter={() => setHovered(i)}
            />
          )
          offset += dash
          return el
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className={`text-xs font-bold ${centerColor || 'text-white'}`}>{centerValue}</span>
        <span className="text-[8px] text-gray-500">{centerLabel}</span>
      </div>

      {/* Hover tooltip */}
      {hovered !== null && tooltipData && tooltipData[hovered] && (
        <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-dark-800 border border-dark-500 rounded-lg px-3 py-2 shadow-lg z-20 whitespace-nowrap pointer-events-none">
          <p className="text-[10px] font-semibold" style={{ color: segments[hovered]?.color }}>
            {tooltipData[hovered].label}
          </p>
          <p className="text-[9px] text-gray-400">{tooltipData[hovered].detail}</p>
        </div>
      )}
    </div>
  )
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
          Strategy Performance
        </h3>
        <p className="text-xs text-gray-500 text-center py-4">No completed trades in the last {days} days</p>
      </div>
    )
  }

  // Group by date
  const byDate = {}
  for (const t of trades) {
    const date = t.date || (t.closed_at || t.placed_at || '').slice(0, 10)
    if (!date) continue
    if (!byDate[date]) byDate[date] = []
    byDate[date].push(t)
  }

  const sortedDates = Object.keys(byDate).sort((a, b) => b.localeCompare(a))
  const today = new Date().toISOString().slice(0, 10)
  const activeDay = expandedDay ?? (sortedDates.includes(today) ? today : sortedDates[0])

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
        <BarChart3 size={16} className={accentClass} />
        Strategy Performance
        <span className="text-[10px] text-gray-500 font-normal">Last {days} days</span>
      </h3>

      <div className="space-y-2">
        {sortedDates.map(date => {
          const dayTrades = byDate[date]
          const isExpanded = activeDay === date
          const dayPnl = dayTrades.reduce((s, t) => s + (t.pnl ?? 0), 0)
          const dayWins = dayTrades.filter(t => (t.pnl ?? 0) > 0).length
          const dayLosses = dayTrades.filter(t => (t.pnl ?? 0) < 0).length
          const dayTotal = dayTrades.length

          const dateLabel = new Date(date + 'T00:00:00').toLocaleDateString('en-IN', {
            weekday: 'short', day: 'numeric', month: 'short'
          })

          // Strategy breakdown
          const stratMap = {}
          for (const t of dayTrades) {
            const key = t.strategy || t.strategy_id || '_unknown'
            if (!stratMap[key]) stratMap[key] = { pnl: 0, count: 0, wins: 0, losses: 0 }
            stratMap[key].pnl += (t.pnl ?? 0)
            stratMap[key].count += 1
            if ((t.pnl ?? 0) > 0) stratMap[key].wins += 1
            else stratMap[key].losses += 1
          }

          const stratEntries = Object.entries(stratMap).sort((a, b) => b[1].pnl - a[1].pnl)

          // Build strategy donut segments + tooltips
          const stratSegments = []
          const stratTooltips = []
          const totalTrades = stratEntries.reduce((s, [, d]) => s + d.count, 0)

          stratEntries.forEach(([key, data], i) => {
            const strat = STRAT_MAP[key]
            const label = strat ? strat.name || strat.shortName : (EXTRA_STRAT_NAMES[key] || key)
            const color = STRAT_COLORS[i % STRAT_COLORS.length]
            const wr = data.count > 0 ? Math.round((data.wins / data.count) * 100) : 0

            stratSegments.push({
              pct: totalTrades > 0 ? (data.count / totalTrades) * 100 : 0,
              color: color,
              hoverColor: color,
            })
            stratTooltips.push({
              label: `${label} — ${wr}% win`,
              detail: `${data.wins}W / ${data.losses}L | P&L: ${data.pnl >= 0 ? '+' : ''}${formatINRCompact(data.pnl)}`,
            })
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
                  <span className="text-[10px] text-gray-500">{dayTotal} trade{dayTotal !== 1 ? 's' : ''}</span>
                  <span className="text-[10px] text-gray-500">{dayWins}W / {dayLosses}L</span>
                </div>
                <span className={`text-xs font-bold tabular-nums ${dayPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {dayPnl >= 0 ? '+' : '-'}{formatINRCompact(dayPnl)}
                </span>
              </button>

              {isExpanded && (
                <div className="px-4 pb-4">
                  {/* Donut Charts Row */}
                  <div className="flex items-center justify-around gap-4 mb-4 py-3 bg-dark-800/50 rounded-xl">
                    {/* Win/Loss Donut */}
                    <Donut
                      size={85}
                      strokeWidth={10}
                      segments={dayTotal > 0 ? [
                        { pct: (dayWins / dayTotal) * 100, color: '#4ade80' },
                        { pct: (dayLosses / dayTotal) * 100, color: '#f87171' },
                      ].filter(s => s.pct > 0) : []}
                      centerValue={dayTotal > 0 ? `${Math.round((dayWins / dayTotal) * 100)}%` : '—'}
                      centerLabel="Win Rate"
                      centerColor={dayWins >= dayLosses ? 'text-green-400' : 'text-red-400'}
                      tooltipData={[
                        { label: `Wins: ${dayWins}`, detail: `${dayWins} profitable trades` },
                        { label: `Losses: ${dayLosses}`, detail: `${dayLosses} losing trades` },
                      ]}
                    />

                    {/* P&L Donut */}
                    <Donut
                      size={85}
                      strokeWidth={10}
                      segments={(() => {
                        const profit = dayTrades.filter(t => (t.pnl ?? 0) > 0).reduce((s, t) => s + t.pnl, 0)
                        const loss = Math.abs(dayTrades.filter(t => (t.pnl ?? 0) < 0).reduce((s, t) => s + t.pnl, 0))
                        const total = profit + loss
                        if (total === 0) return []
                        return [
                          { pct: (profit / total) * 100, color: '#4ade80' },
                          { pct: (loss / total) * 100, color: '#f87171' },
                        ].filter(s => s.pct > 0)
                      })()}
                      centerValue={`${dayPnl >= 0 ? '+' : ''}${formatINRCompact(dayPnl)}`}
                      centerLabel="Net P&L"
                      centerColor={dayPnl >= 0 ? 'text-green-400' : 'text-red-400'}
                      tooltipData={[
                        { label: `Profit: +${formatINRCompact(dayTrades.filter(t => (t.pnl ?? 0) > 0).reduce((s, t) => s + t.pnl, 0))}`, detail: `${dayWins} winning trades` },
                        { label: `Loss: -${formatINRCompact(Math.abs(dayTrades.filter(t => (t.pnl ?? 0) < 0).reduce((s, t) => s + t.pnl, 0)))}`, detail: `${dayLosses} losing trades` },
                      ]}
                    />

                    {/* Strategy Win% Donut — hover shows per-strategy details */}
                    <Donut
                      size={85}
                      strokeWidth={10}
                      segments={stratSegments}
                      centerValue={`${stratEntries.length}`}
                      centerLabel={stratEntries.length === 1 ? 'Strategy' : 'Strategies'}
                      centerColor="text-white"
                      tooltipData={stratTooltips}
                    />
                  </div>

                  {/* Strategy Breakdown — compact cards (hover donuts for details) */}
                  <div className="space-y-1.5">
                    {stratEntries.map(([key, data], i) => {
                      const strat = STRAT_MAP[key]
                      const label = strat ? strat.name || strat.shortName : (EXTRA_STRAT_NAMES[key] || key)
                      const color = STRAT_COLORS[i % STRAT_COLORS.length]
                      const wr = data.count > 0 ? Math.round((data.wins / data.count) * 100) : 0

                      return (
                        <div key={key} className="flex items-center gap-3 bg-dark-800/50 rounded-lg px-3 py-2">
                          <div className="w-1.5 h-6 rounded-full" style={{ backgroundColor: color }} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-medium text-white truncate">{label}</span>
                              <span className={`text-[11px] font-bold tabular-nums ${data.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {data.pnl >= 0 ? '+' : ''}{formatINRCompact(data.pnl)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-[9px] text-gray-500">
                              <span>{data.count} trade{data.count !== 1 ? 's' : ''}</span>
                              <span>{data.wins}W/{data.losses}L</span>
                              <span>{wr}%</span>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
