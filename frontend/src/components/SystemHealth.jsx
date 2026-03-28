import React, { useState, useEffect } from 'react'
import { Heart, Wifi, WifiOff, Clock, Server, Shield, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { getAuthToken } from '../services/api/base'

function authFetch(url) {
  const token = getAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  return fetch(url, { headers }).then(r => r.json()).catch(() => null)
}

function StatusDot({ ok, label }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'} ${ok ? '' : 'animate-pulse'}`} />
      <span className="text-[10px] text-gray-400">{label}</span>
      {ok ? <CheckCircle size={10} className="text-emerald-400" /> : <XCircle size={10} className="text-red-400" />}
    </div>
  )
}

export default function SystemHealth() {
  const [data, setData] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  useEffect(() => {
    check()
    const id = setInterval(check, 30000)
    return () => clearInterval(id)
  }, [])

  async function check() {
    try {
      const [fyers, eq, opt, btst, market, funds, monitor] = await Promise.all([
        authFetch('/api/fyers/status'),
        authFetch('/api/auto/status'),
        authFetch('/api/options/auto/status'),
        authFetch('/api/btst/status'),
        authFetch('/api/market-status'),
        authFetch('/api/fyers/funds'),
        authFetch('/api/monitor/log'),
      ])

      let available = 0
      for (const f of (funds?.fund_limit || [])) {
        if (f.id === 10) available = f.equityAmount || 0
      }

      // Count errors in monitor log
      const logs = monitor?.log || []
      const recentErrors = logs.filter(l =>
        typeof l === 'string' ? l.includes('ERROR') || l.includes('FAIL') :
        (l.level || '').includes('ERROR') || (l.level || '').includes('FAIL')
      ).length

      setData({
        fyers: fyers?.connected === true || fyers?.profile?.name,
        fyersName: fyers?.profile?.name || '',
        eqRunning: eq?.is_running || false,
        eqScans: eq?.scan_count || 0,
        eqOrders: eq?.order_count || 0,
        eqActive: (eq?.active_trades || []).length,
        optRunning: opt?.is_running || false,
        optScans: opt?.scan_count || 0,
        optPositions: (opt?.active_positions || []).length,
        btstRunning: btst?.is_running || false,
        btstScans: btst?.scan_count || 0,
        btstActive: (btst?.active_trades || []).length,
        marketOpen: market?.is_open || false,
        available,
        recentErrors,
        monitorLogs: logs.slice(-5),
      })
      setLastUpdate(new Date())
    } catch {}
  }

  if (!data) return null

  const allEnginesOk = data.eqRunning || data.optRunning || data.btstRunning || !data.marketOpen
  const overall = data.fyers && allEnginesOk && data.recentErrors === 0

  return (
    <div className="rounded-2xl border border-dark-500 overflow-hidden">
      {/* Header */}
      <div className={`px-5 py-3 flex items-center justify-between ${overall ? 'bg-gradient-to-r from-emerald-500/10 via-dark-800 to-emerald-500/5' : 'bg-gradient-to-r from-red-500/10 via-dark-800 to-red-500/5'}`}>
        <div className="flex items-center gap-2">
          <Heart size={16} className={overall ? 'text-emerald-400' : 'text-red-400'} />
          <h3 className="text-sm font-semibold text-white">System Health</h3>
          <span className={`text-[9px] px-2 py-0.5 rounded font-bold ${overall ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
            {overall ? 'HEALTHY' : 'ISSUES'}
          </span>
        </div>
        <span className="text-[9px] text-gray-500">
          {lastUpdate ? `Updated ${lastUpdate.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : '...'} · auto 30s
        </span>
      </div>

      {/* Status grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-dark-500">
        {/* Fyers */}
        <div className="bg-dark-800 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            {data.fyers ? <Wifi size={12} className="text-emerald-400" /> : <WifiOff size={12} className="text-red-400" />}
            <span className="text-[10px] font-semibold text-white">Fyers</span>
          </div>
          <StatusDot ok={data.fyers} label={data.fyers ? 'Connected' : 'Disconnected'} />
          {data.fyersName && <p className="text-[9px] text-gray-500 mt-1">{data.fyersName}</p>}
          <p className="text-[9px] text-gray-500">Margin: ₹{(data.available || 0).toLocaleString('en-IN')}</p>
        </div>

        {/* Equity Engine */}
        <div className="bg-dark-800 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Server size={12} className="text-green-400" />
            <span className="text-[10px] font-semibold text-white">Equity</span>
          </div>
          <StatusDot ok={data.eqRunning} label={data.eqRunning ? 'Running' : 'Stopped'} />
          <p className="text-[9px] text-gray-500 mt-1">Scans: {data.eqScans} · Orders: {data.eqOrders}</p>
          <p className="text-[9px] text-gray-500">Active: {data.eqActive} positions</p>
        </div>

        {/* Options Engine */}
        <div className="bg-dark-800 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Server size={12} className="text-violet-400" />
            <span className="text-[10px] font-semibold text-white">Options</span>
          </div>
          <StatusDot ok={data.optRunning} label={data.optRunning ? 'Running' : 'Stopped'} />
          <p className="text-[9px] text-gray-500 mt-1">Scans: {data.optScans}</p>
          <p className="text-[9px] text-gray-500">Spreads: {data.optPositions} open</p>
        </div>

        {/* BTST Engine */}
        <div className="bg-dark-800 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Server size={12} className="text-amber-400" />
            <span className="text-[10px] font-semibold text-white">BTST</span>
          </div>
          <StatusDot ok={data.btstRunning} label={data.btstRunning ? 'Running' : 'Stopped'} />
          <p className="text-[9px] text-gray-500 mt-1">Scans: {data.btstScans}</p>
          <p className="text-[9px] text-gray-500">Holdings: {data.btstActive}</p>
        </div>
      </div>

      {/* Bottom bar — market + errors */}
      <div className="px-5 py-2 bg-dark-700 flex items-center justify-between border-t border-dark-500">
        <div className="flex items-center gap-3">
          <StatusDot ok={data.marketOpen} label={data.marketOpen ? 'Market Open' : 'Market Closed'} />
          <StatusDot ok={data.recentErrors === 0} label={data.recentErrors === 0 ? 'No errors' : `${data.recentErrors} errors in log`} />
        </div>
        <div className="flex items-center gap-1.5">
          <Shield size={10} className="text-gray-500" />
          <span className="text-[9px] text-gray-500">SL on exchange · flash crash protection · force-close active</span>
        </div>
      </div>
    </div>
  )
}
