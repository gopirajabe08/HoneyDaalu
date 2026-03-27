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
      const [eqRegime, futRegime, optRegime, eqStatus, optStatus, futStatus, eqLive, optLive, monitor] = await Promise.all([
        authFetch(`${API}/api/equity/regime`),
        authFetch(`${API}/api/futures/regime`),
        authFetch(`${API}/api/options/regime`),
        authFetch(`${API}/api/paper/status`),
        authFetch(`${API}/api/options/paper/status`),
        authFetch(`${API}/api/futures/paper/status`),
        authFetch(`${API}/api/auto/status`),
        authFetch(`${API}/api/options/auto/status`),
        authFetch(`${API}/api/monitor/log`),
      ])
      setData({ eqRegime, futRegime, optRegime, eqStatus, optStatus, futStatus, eqLive, optLive, monitor })
    } catch {}
  }

  if (!data) return null

  const { eqRegime, futRegime, optRegime, eqStatus, optStatus, futStatus, eqLive, optLive, monitor } = data
  const vix = eqRegime?.components?.vix || 0
  const niftyChange = eqRegime?.components?.intraday?.change_pct || 0
  const confidence = eqRegime?.confidence || '?'

  // Calculate total P&L across all engines
  const paperPnl = (eqStatus?.total_pnl || 0) + (optStatus?.total_pnl || 0) + (futStatus?.total_pnl || 0)
  const livePnl = (eqLive?.total_pnl || 0) + (optLive?.total_pnl || 0)
  const totalTrades = (eqStatus?.order_count || 0) + (optStatus?.order_count || 0) + (futStatus?.order_count || 0)
  const liveTrades = (eqLive?.order_count || 0) + (optLive?.order_count || 0)

  // Recent monitor decisions
  const monitorLogs = (monitor?.log || []).slice(-5)

  const vixColor = vix > 20 ? 'text-red-400' : vix > 16 ? 'text-yellow-400' : 'text-emerald-400'
  const confColor = confidence === 'high' ? 'text-emerald-400' : confidence === 'medium' ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="bg-gradient-to-r from-dark-700 via-dark-800 to-dark-700 rounded-2xl border border-dark-500 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">&#x1F9E0;</span>
          <h3 className="text-sm font-bold text-white">System Brain</h3>
          <span className="text-[9px] bg-dark-600 text-gray-400 px-2 py-0.5 rounded">LIVE - refreshes 30s</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className={vixColor}>VIX {vix}</span>
          <span className={niftyChange >= 0 ? 'text-emerald-400' : 'text-red-400'}>NIFTY {niftyChange >= 0 ? '+' : ''}{niftyChange.toFixed(2)}%</span>
          <span className={confColor}>&#x25CF; {confidence}</span>
        </div>
      </div>

      {/* Regime Row */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="bg-dark-600/50 rounded-lg px-3 py-2 border border-dark-500/30">
          <p className="text-[9px] text-orange-400 font-semibold mb-1">EQUITY</p>
          <p className="text-[10px] text-white">{(eqRegime?.regime || '?').replace(/_/g, ' ').slice(0, 30)}</p>
          <p className="text-[9px] text-gray-500">{(eqRegime?.strategy_ids || []).length} strategies</p>
        </div>
        <div className="bg-dark-600/50 rounded-lg px-3 py-2 border border-dark-500/30">
          <p className="text-[9px] text-amber-400 font-semibold mb-1">FUTURES</p>
          <p className="text-[10px] text-white">{(futRegime?.regime || '?').replace(/_/g, ' ').slice(0, 30)}</p>
          <p className="text-[9px] text-gray-500">{(futRegime?.strategy_ids || futRegime?.strategies || []).length} strategies</p>
        </div>
        <div className="bg-dark-600/50 rounded-lg px-3 py-2 border border-dark-500/30">
          <p className="text-[9px] text-violet-400 font-semibold mb-1">OPTIONS</p>
          <p className="text-[10px] text-white">{(optRegime?.conviction || '?').replace(/_/g, ' ')}</p>
          <p className="text-[9px] text-gray-500">{(optRegime?.recommended_strategies || []).join(', ')}</p>
        </div>
      </div>

      {/* P&L + Trades Row */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div className="text-center bg-dark-600/30 rounded-lg py-1.5">
          <p className="text-[9px] text-gray-500">Paper P&L</p>
          <p className={`text-sm font-bold ${paperPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>&#x20B9;{Math.round(paperPnl).toLocaleString('en-IN')}</p>
        </div>
        <div className="text-center bg-dark-600/30 rounded-lg py-1.5">
          <p className="text-[9px] text-gray-500">Live P&L</p>
          <p className={`text-sm font-bold ${livePnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>&#x20B9;{Math.round(livePnl).toLocaleString('en-IN')}</p>
        </div>
        <div className="text-center bg-dark-600/30 rounded-lg py-1.5">
          <p className="text-[9px] text-gray-500">Paper Trades</p>
          <p className="text-sm font-bold text-white">{totalTrades}</p>
        </div>
        <div className="text-center bg-dark-600/30 rounded-lg py-1.5">
          <p className="text-[9px] text-gray-500">Live Trades</p>
          <p className="text-sm font-bold text-white">{liveTrades}</p>
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
