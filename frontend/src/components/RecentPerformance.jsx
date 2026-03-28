import React, { useState, useEffect } from 'react'
import { Calendar, TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react'
import { getAuthToken } from '../services/api/base'

export default function RecentPerformance() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const token = getAuthToken()
        const headers = token ? { Authorization: `Bearer ${token}` } : {}
        const res = await fetch('/api/tracking/recent?days=7', { headers })
        const data = await res.json()
        const arr = Array.isArray(data) ? data : (data?.reports || [])
        setReports(arr)
      } catch {}
      setLoading(false)
    }
    load()
  }, [])

  if (loading) return null
  if (!reports.length) return null

  const pnlColor = (v) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-500'
  const PnlIcon = ({ v }) => v > 0 ? <TrendingUp size={14} /> : v < 0 ? <TrendingDown size={14} /> : <Minus size={14} />
  const inr = (v) => `${v >= 0 ? '+' : ''}₹${Math.abs(Math.round(v)).toLocaleString('en-IN')}`

  // Calculate running total
  let runningTotal = 0
  const rows = reports.map(r => {
    const date = r.date || '?'
    const trades = r.total_trades || 0
    const pnl = r.total_net_pnl || 0
    runningTotal += pnl

    // Get source breakdown
    const src = r.source_pnl_summary || {}
    let livePnl = 0
    let paperPnl = 0
    if (typeof src === 'object') {
      for (const [k, v] of Object.entries(src)) {
        const val = typeof v === 'number' ? v : (v?.net_pnl || 0)
        if (k === 'auto' || k === 'options_auto' || k === 'btst') livePnl += val
        else paperPnl += val
      }
    }

    return { date, trades, pnl, livePnl, paperPnl, runningTotal }
  }).reverse()

  const totalPnl = rows.reduce((s, r) => s + r.pnl, 0)
  const totalTrades = rows.reduce((s, r) => s + r.trades, 0)
  const winDays = rows.filter(r => r.pnl > 0).length
  const lossDays = rows.filter(r => r.pnl < 0).length

  return (
    <div className="rounded-2xl border border-dark-500 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 bg-dark-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar size={16} className="text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Recent Performance</h3>
          <span className="text-[9px] bg-dark-600 text-gray-400 px-2 py-0.5 rounded">OFFLINE — saved data</span>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-gray-500">{rows.length} days</span>
          <span className="text-gray-500">{totalTrades} trades</span>
          <span className={pnlColor(totalPnl)}>{inr(totalPnl)}</span>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 divide-x divide-dark-500 bg-dark-800">
        <div className="px-4 py-2.5 text-center">
          <p className="text-[9px] text-gray-500">7-Day P&L</p>
          <p className={`text-base font-bold ${pnlColor(totalPnl)}`}>{inr(totalPnl)}</p>
        </div>
        <div className="px-4 py-2.5 text-center">
          <p className="text-[9px] text-gray-500">Total Trades</p>
          <p className="text-base font-bold text-white">{totalTrades}</p>
        </div>
        <div className="px-4 py-2.5 text-center">
          <p className="text-[9px] text-gray-500">Win Days</p>
          <p className="text-base font-bold text-emerald-400">{winDays}</p>
        </div>
        <div className="px-4 py-2.5 text-center">
          <p className="text-[9px] text-gray-500">Loss Days</p>
          <p className="text-base font-bold text-red-400">{lossDays}</p>
        </div>
      </div>

      {/* Daily breakdown table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-dark-700 border-y border-dark-500">
              {['Date', 'Trades', 'Live P&L', 'Paper P&L', 'Day Total', 'Cumulative'].map(h => (
                <th key={h} className="text-[10px] text-gray-500 font-medium text-right py-2 px-3 first:text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={`border-b border-dark-600/50 hover:bg-dark-700/50 ${r.pnl > 0 ? 'bg-emerald-500/3' : r.pnl < 0 ? 'bg-red-500/3' : ''}`}>
                <td className="py-2 px-3 text-xs text-white">{r.date}</td>
                <td className="py-2 px-3 text-xs text-gray-400 text-right">{r.trades}</td>
                <td className={`py-2 px-3 text-xs text-right font-medium ${pnlColor(r.livePnl)}`}>{inr(r.livePnl)}</td>
                <td className="py-2 px-3 text-xs text-right text-gray-500">{inr(r.paperPnl)}</td>
                <td className={`py-2 px-3 text-xs text-right font-semibold ${pnlColor(r.pnl)}`}>
                  <span className="inline-flex items-center gap-1">
                    <PnlIcon v={r.pnl} />
                    {inr(r.pnl)}
                  </span>
                </td>
                <td className={`py-2 px-3 text-xs text-right font-medium ${pnlColor(r.runningTotal)}`}>{inr(r.runningTotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
