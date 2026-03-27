import React, { useState, useEffect } from 'react'
import { getAuthToken } from '../services/api/base'

const API = 'http://localhost:8001'

function authFetch(url) {
  const token = getAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  return fetch(url, { headers }).then(r => r.json()).catch(() => null)
}

export default function SystemBrain() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 30000)
    return () => clearInterval(id)
  }, [])

  async function fetchData() {
    try {
      const [eqRegime, eqLive, optLive, btstLive, positions, monitor] = await Promise.all([
        authFetch(`${API}/api/equity/regime`),
        authFetch(`${API}/api/auto/status`),
        authFetch(`${API}/api/options/auto/status`),
        authFetch(`${API}/api/btst/status`),
        authFetch(`${API}/api/fyers/positions`),
        authFetch(`${API}/api/monitor/log`),
      ])

      // Calculate Fyers P&L per type
      const posArr = positions?.netPositions || positions?.data?.netPositions || []
      let eqFyersPnl = 0, optFyersPnl = 0, btstFyersPnl = 0
      let eqOpenCount = 0, optOpenCount = 0, btstOpenCount = 0
      let eqClosedCount = 0, optClosedCount = 0, btstClosedCount = 0

      for (const p of posArr) {
        const sym = (p.symbol || '').toUpperCase()
        const pnl = p.pl || 0
        const traded = (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0
        if (!traded) continue

        const isOption = sym.includes('CE') || sym.includes('PE')
        const isCNC = (p.productType || '') === 'CNC'
        const isOpen = (p.netQty || 0) !== 0

        if (isCNC) {
          btstFyersPnl += pnl
          if (isOpen) btstOpenCount++; else btstClosedCount++
        } else if (isOption) {
          optFyersPnl += pnl
          if (isOpen) optOpenCount++; else optClosedCount++
        } else {
          eqFyersPnl += pnl
          if (isOpen) eqOpenCount++; else eqClosedCount++
        }
      }

      setData({
        eqRegime,
        eqLive, optLive, btstLive,
        eqFyersPnl, optFyersPnl, btstFyersPnl,
        eqOpenCount, optOpenCount, btstOpenCount,
        eqClosedCount, optClosedCount, btstClosedCount,
        monitor,
      })
    } catch {}
  }

  if (!data) return null

  const { eqRegime, eqLive, optLive, btstLive } = data
  const vix = eqRegime?.components?.vix || 0
  const niftyChange = eqRegime?.components?.intraday?.change_pct || 0
  const confidence = eqRegime?.confidence || '?'
  const regime = (eqRegime?.regime || '?').replace(/_/g, ' ')

  const totalFyersPnl = data.eqFyersPnl + data.optFyersPnl + data.btstFyersPnl
  const totalOpen = data.eqOpenCount + data.optOpenCount + data.btstOpenCount
  const totalClosed = data.eqClosedCount + data.optClosedCount + data.btstClosedCount
  const totalCharges = totalClosed * 65

  const vixColor = vix > 20 ? 'text-red-400' : vix > 16 ? 'text-yellow-400' : 'text-emerald-400'
  const confColor = confidence === 'high' ? 'text-emerald-400' : confidence === 'medium' ? 'text-yellow-400' : 'text-red-400'
  const pnlColor = (v) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-400'
  const inr = (v) => `₹${Math.round(v).toLocaleString('en-IN')}`

  const monitorLogs = (data.monitor?.log || []).slice(-5)

  return (
    <div className="bg-gradient-to-r from-dark-700 via-dark-800 to-dark-700 rounded-2xl border border-dark-500 p-4 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">&#x1F9E0;</span>
          <h3 className="text-sm font-bold text-white">System Brain</h3>
          <span className="text-[9px] bg-dark-600 text-gray-400 px-2 py-0.5 rounded">FYERS LIVE</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className={vixColor}>VIX {vix}</span>
          <span className={niftyChange >= 0 ? 'text-emerald-400' : 'text-red-400'}>
            NIFTY {niftyChange >= 0 ? '+' : ''}{niftyChange.toFixed(2)}%
          </span>
          <span className={confColor}>&#x25CF; {confidence}</span>
        </div>
      </div>

      {/* Regime + strategies */}
      <div className="bg-dark-600/30 rounded-lg px-3 py-2 mb-3 flex items-center justify-between">
        <div>
          <span className="text-[9px] text-gray-500">Regime: </span>
          <span className="text-[10px] text-white font-medium">{regime}</span>
        </div>
        <span className="text-[9px] text-gray-500">{(eqRegime?.strategy_ids || []).length} strategies active</span>
      </div>

      {/* Live P&L per engine — FROM FYERS */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="bg-dark-600/30 rounded-lg p-2.5 border border-dark-500/30">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] text-violet-400 font-semibold">OPTIONS</span>
            {optLive?.is_running && <span className="text-[8px] text-green-400">● LIVE</span>}
          </div>
          <p className={`text-sm font-bold ${pnlColor(data.optFyersPnl)}`}>{inr(data.optFyersPnl)}</p>
          <p className="text-[9px] text-gray-500">{data.optOpenCount} open · {data.optClosedCount} closed</p>
        </div>
        <div className="bg-dark-600/30 rounded-lg p-2.5 border border-dark-500/30">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] text-green-400 font-semibold">EQUITY</span>
            {eqLive?.is_running && <span className="text-[8px] text-green-400">● LIVE</span>}
          </div>
          <p className={`text-sm font-bold ${pnlColor(data.eqFyersPnl)}`}>{inr(data.eqFyersPnl)}</p>
          <p className="text-[9px] text-gray-500">{data.eqOpenCount} open · {data.eqClosedCount} closed</p>
        </div>
        <div className="bg-dark-600/30 rounded-lg p-2.5 border border-dark-500/30">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] text-amber-400 font-semibold">BTST</span>
            {btstLive?.is_running && <span className="text-[8px] text-green-400">● LIVE</span>}
          </div>
          <p className={`text-sm font-bold ${pnlColor(data.btstFyersPnl)}`}>{inr(data.btstFyersPnl)}</p>
          <p className="text-[9px] text-gray-500">{data.btstOpenCount} open · {data.btstClosedCount} closed</p>
        </div>
      </div>

      {/* Total row */}
      <div className="flex items-center justify-between bg-dark-600/50 rounded-lg px-3 py-2 mb-3 border border-dark-500/30">
        <div>
          <span className="text-[9px] text-gray-500">Total Fyers P&L</span>
          <p className={`text-lg font-bold ${pnlColor(totalFyersPnl)}`}>{inr(totalFyersPnl)}</p>
        </div>
        <div className="text-right">
          <p className="text-[9px] text-gray-500">{totalOpen} open · {totalClosed} closed</p>
          <p className="text-[9px] text-gray-500">Est. charges: {inr(totalCharges)}</p>
          <p className={`text-xs font-semibold ${pnlColor(totalFyersPnl - totalCharges)}`}>
            Net: {inr(totalFyersPnl - totalCharges)}
          </p>
        </div>
      </div>

      {/* Monitor Decisions */}
      {monitorLogs.length > 0 && (
        <div>
          <p className="text-[9px] text-gray-500 mb-1">Recent System Decisions:</p>
          <div className="space-y-0.5 max-h-[60px] overflow-y-auto">
            {monitorLogs.map((log, i) => (
              <p key={i} className="text-[9px] text-gray-400 truncate">{log}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
