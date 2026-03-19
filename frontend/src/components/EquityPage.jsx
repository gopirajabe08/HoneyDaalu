import React, { useState } from 'react'
import { Briefcase, Zap, FlaskConical, Repeat, Activity } from 'lucide-react'
import IntradayTrade from './IntradayTrade'
import SwingTrade from './SwingTrade'

const tabs = [
  { id: 'intraday-paper', label: 'Intraday Paper', icon: FlaskConical, component: 'intraday', mode: 'paper', color: 'blue' },
  { id: 'intraday-live', label: 'Intraday Live', icon: Zap, component: 'intraday', mode: 'live', color: 'orange' },
  { id: 'swing-paper', label: 'Swing Paper', icon: Activity, component: 'swing', mode: 'paper', color: 'teal' },
  { id: 'swing-live', label: 'Swing Live', icon: Repeat, component: 'swing', mode: 'live', color: 'emerald' },
]

const TAB_COLORS = {
  blue: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  orange: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  teal: 'bg-teal-500/20 text-teal-400 border border-teal-500/30',
  emerald: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
}

export default function EquityPage({ capital, setCapital }) {
  const [activeTab, setActiveTab] = useState('intraday-live')

  const current = tabs.find(t => t.id === activeTab)

  return (
    <div className="space-y-5">
      {/* Header + Tab bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Briefcase size={22} className="text-orange-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Equity Trading</h2>
            <p className="text-gray-500 text-xs">Nifty 500 stock strategies with intraday & swing modes</p>
          </div>
        </div>

        <div className="flex items-center bg-dark-700 rounded-xl p-1 border border-dark-500">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === tab.id
                  ? TAB_COLORS[tab.color]
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <tab.icon size={12} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Quick Start Guide */}
      <div className="flex items-center gap-3 bg-dark-700/30 rounded-lg px-4 py-1.5 border border-dark-600/50 text-[10px] text-gray-500">
        <span className="text-white font-semibold">Quick Start</span>
        <span className="text-dark-500">|</span>
        {current?.component === 'intraday' ? (
          <>
            <span>Start at <span className="text-orange-400 font-semibold">10:15 AM</span></span>
            <span className="text-dark-500">|</span>
            <span>Capital: <span className="text-white">₹75K</span> (paper)</span>
            <span className="text-dark-500">|</span>
            <span>Mode: <span className="text-amber-400">Auto Regime</span> (dynamic re-detection)</span>
            <span className="text-dark-500">|</span>
            <span>Orders: 10:30 AM - 2:00 PM | Square-off 3:15 PM</span>
          </>
        ) : (
          <>
            <span>Start at <span className="text-emerald-400 font-semibold">9:15 AM</span></span>
            <span className="text-dark-500">|</span>
            <span>Capital: <span className="text-white">₹75K</span> (paper)</span>
            <span className="text-dark-500">|</span>
            <span>Mode: <span className="text-white">Auto Regime</span> (Play 1, 2, 4, 5, 6 on 1d)</span>
            <span className="text-dark-500">|</span>
            <span>Scan: 9:20 AM + retry 2h | Positions carry overnight</span>
          </>
        )}
      </div>

      {/* Timing Reference */}
      {current?.component === 'intraday' ? (
        <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-dark-600 text-[10px] text-gray-500">
          <span className="text-orange-400 font-semibold">Intraday</span>
          <span className="text-dark-500">|</span>
          <span>Regime: <span className="text-amber-400">Auto</span> (NIFTY + VIX + ADX picks strategies)</span>
          <span className="text-dark-500">|</span>
          <span>Scan: <span className="text-orange-400">10:30 AM</span> + on-demand when slot opens</span>
          <span className="text-dark-500">|</span>
          <span>Orders: <span className="text-orange-400">10:30 AM - 2:00 PM</span></span>
          <span className="text-dark-500">|</span>
          <span>Max: <span className="text-white">2 orders/scan</span> (staggered)</span>
          <span className="text-dark-500">|</span>
          <span>Monitor: <span className="text-white">every 20s</span></span>
          <span className="text-dark-500">|</span>
          <span>Square-off: <span className="text-red-400">3:15 PM</span></span>
          <span className="text-dark-500">|</span>
          <span>SL: <span className="text-white">min 1.2%</span></span>
          <span className="text-dark-500">|</span>
          <span>Trailing SL: <span className="text-white">+1% → 50% trail</span></span>
          <span className="text-dark-500">|</span>
          <span>VIX {'>'} 18: <span className="text-yellow-400">15m only</span></span>
          <span className="text-dark-500">|</span>
          <span>Daily loss: <span className="text-red-400">5% cap</span></span>
          <span className="text-dark-500">|</span>
          <span>Drawdown: <span className="text-red-400">15%/5d breaker</span></span>
          <span className="text-dark-500">|</span>
          <span>Positions: <span className="text-white">6 live / 10 paper</span></span>
          <span className="text-dark-500">|</span>
          <span>Nifty 500 | ₹50-₹5,000</span>
        </div>
      ) : (
        <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-emerald-500/10 text-[10px] text-gray-500">
          <span className="text-emerald-400 font-semibold">Swing</span>
          <span className="text-dark-500">|</span>
          <span>Scan: <span className="text-emerald-400">9:20 AM</span> (retry every 2h until 2 PM)</span>
          <span className="text-dark-500">|</span>
          <span>Monitor: <span className="text-white">every 5 min</span></span>
          <span className="text-dark-500">|</span>
          <span>Direction: <span className="text-white">BUY only</span> (CNC)</span>
          <span className="text-dark-500">|</span>
          <span>SL: <span className="text-white">min 1.2%</span></span>
          <span className="text-dark-500">|</span>
          <span>Trailing SL: <span className="text-white">+1% → 50% trail</span></span>
          <span className="text-dark-500">|</span>
          <span>Positions: <span className="text-white">1 live / 5 paper</span></span>
          <span className="text-dark-500">|</span>
          <span>₹100-₹1,500 | SL/Target re-placed daily</span>
          <span className="text-dark-500">|</span>
          <span>Nifty Filter: blocks BUY when Nifty {'<'} 50 SMA</span>
        </div>
      )}

      {/* Active component — key forces remount on tab switch */}
      {current?.component === 'intraday' ? (
        <IntradayTrade key={current.id} mode={current.mode} capital={capital} setCapital={setCapital} />
      ) : (
        <SwingTrade key={current.id} mode={current.mode} capital={capital} setCapital={setCapital} />
      )}
    </div>
  )
}
