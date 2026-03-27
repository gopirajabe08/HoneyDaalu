import React, { useState, useEffect } from 'react'
import { Brain, TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react'
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
      const [eqRegime, eqLive, optLive, btstLive, positions] = await Promise.all([
        authFetch(`${API}/api/equity/regime`),
        authFetch(`${API}/api/auto/status`),
        authFetch(`${API}/api/options/auto/status`),
        authFetch(`${API}/api/btst/status`),
        authFetch(`${API}/api/fyers/positions`),
      ])

      const posArr = positions?.netPositions || positions?.data?.netPositions || []
      let eqPnl = 0, optPnl = 0, btstPnl = 0
      let eqOpen = 0, optOpen = 0, btstOpen = 0
      let eqClosed = 0, optClosed = 0, btstClosed = 0

      for (const p of posArr) {
        const sym = (p.symbol || '').toUpperCase()
        const pnl = p.pl || 0
        const traded = (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0
        if (!traded) continue
        const isOpt = sym.includes('CE') || sym.includes('PE')
        const isCNC = (p.productType || '') === 'CNC'
        const open = (p.netQty || 0) !== 0

        if (isCNC) { btstPnl += pnl; open ? btstOpen++ : btstClosed++ }
        else if (isOpt) { optPnl += pnl; open ? optOpen++ : optClosed++ }
        else { eqPnl += pnl; open ? eqOpen++ : eqClosed++ }
      }

      setData({ eqRegime, eqLive, optLive, btstLive, eqPnl, optPnl, btstPnl, eqOpen, optOpen, btstOpen, eqClosed, optClosed, btstClosed })
    } catch {}
  }

  if (!data) return null

  const vix = data.eqRegime?.components?.vix || 0
  const nifty = data.eqRegime?.components?.intraday?.change_pct || 0
  const regime = (data.eqRegime?.regime || '').replace(/_/g, ' ')
  const strategies = (data.eqRegime?.strategy_ids || []).length
  const totalPnl = data.eqPnl + data.optPnl + data.btstPnl
  const totalOpen = data.eqOpen + data.optOpen + data.btstOpen
  const totalClosed = data.eqClosed + data.optClosed + data.btstClosed
  const charges = totalClosed * 65
  const netPnl = totalPnl - charges

  const PnlIcon = ({ v }) => v > 0 ? <TrendingUp size={12} /> : v < 0 ? <TrendingDown size={12} /> : <Minus size={12} />
  const pnlCls = (v) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-500'
  const inr = (v) => `${v >= 0 ? '+' : ''}₹${Math.abs(Math.round(v)).toLocaleString('en-IN')}`

  const engines = [
    { label: 'Options', pnl: data.optPnl, open: data.optOpen, closed: data.optClosed, running: data.optLive?.is_running, color: 'violet', gradient: 'from-violet-500/10 to-violet-500/5' },
    { label: 'Equity', pnl: data.eqPnl, open: data.eqOpen, closed: data.eqClosed, running: data.eqLive?.is_running, color: 'emerald', gradient: 'from-emerald-500/10 to-emerald-500/5' },
    { label: 'BTST', pnl: data.btstPnl, open: data.btstOpen, closed: data.btstClosed, running: data.btstLive?.is_running, color: 'amber', gradient: 'from-amber-500/10 to-amber-500/5' },
  ]

  return (
    <div className="rounded-2xl border border-dark-500 overflow-hidden mb-4">
      {/* Top banner — gradient based on P&L */}
      <div className={`px-5 py-3 ${totalPnl >= 0 ? 'bg-gradient-to-r from-emerald-500/15 via-dark-800 to-emerald-500/5' : 'bg-gradient-to-r from-red-500/15 via-dark-800 to-red-500/5'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${totalPnl >= 0 ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
              <Activity size={18} className={totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'} />
            </div>
            <div>
              <p className="text-xs text-gray-400">Today's Live P&L (Fyers)</p>
              <p className={`text-xl font-bold tracking-tight ${pnlCls(totalPnl)}`}>{inr(totalPnl)}</p>
            </div>
          </div>
          <div className="text-right space-y-0.5">
            <div className="flex items-center gap-2 text-[10px]">
              <span className={vix > 20 ? 'text-red-400' : vix > 16 ? 'text-yellow-400' : 'text-emerald-400'}>
                VIX {vix}
              </span>
              <span className="text-dark-500">|</span>
              <span className={nifty >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                NIFTY {nifty >= 0 ? '+' : ''}{nifty.toFixed(1)}%
              </span>
            </div>
            <p className="text-[9px] text-gray-500 capitalize">{regime} · {strategies} strategies</p>
            <p className="text-[9px] text-gray-500">{totalOpen} open · {totalClosed} closed · charges {inr(charges).replace('+', '')}</p>
          </div>
        </div>
      </div>

      {/* Engine cards */}
      <div className="grid grid-cols-3 divide-x divide-dark-500">
        {engines.map(e => (
          <div key={e.label} className={`px-4 py-3 bg-gradient-to-b ${e.gradient}`}>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-[10px] font-bold text-${e.color}-400 uppercase tracking-wider`}>{e.label}</span>
              {e.running ? (
                <span className="flex items-center gap-1 text-[8px] text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  LIVE
                </span>
              ) : (
                <span className="text-[8px] text-gray-600">OFF</span>
              )}
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className={pnlCls(e.pnl)}><PnlIcon v={e.pnl} /></span>
              <span className={`text-base font-bold ${pnlCls(e.pnl)}`}>{inr(e.pnl)}</span>
            </div>
            <p className="text-[9px] text-gray-500 mt-1">{e.open} open · {e.closed} closed</p>
          </div>
        ))}
      </div>

      {/* Net P&L bar */}
      <div className={`px-5 py-2 flex items-center justify-between border-t border-dark-500 ${netPnl >= 0 ? 'bg-emerald-500/5' : 'bg-red-500/5'}`}>
        <span className="text-[10px] text-gray-500">Net after charges</span>
        <span className={`text-sm font-bold ${pnlCls(netPnl)}`}>{inr(netPnl)}</span>
      </div>
    </div>
  )
}
