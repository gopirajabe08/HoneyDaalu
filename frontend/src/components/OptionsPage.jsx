import React, { useState } from 'react'
import { TrendingUp, Zap, Repeat, FlaskConical, Activity } from 'lucide-react'
import OptionsIntradayTrade from './OptionsIntradayTrade'
import OptionsSwingTrade from './OptionsSwingTrade'

const tabs = [
  { id: 'intraday-paper', label: 'Intraday Paper', icon: FlaskConical, component: 'intraday', mode: 'paper', color: 'blue' },
  { id: 'intraday-live', label: 'Intraday Live', icon: Zap, component: 'intraday', mode: 'live', color: 'orange' },
  { id: 'swing-paper', label: 'Swing Paper', icon: Activity, component: 'swing', mode: 'paper', color: 'teal' },
  { id: 'swing-live', label: 'Swing Live', icon: Repeat, component: 'swing', mode: 'live', color: 'emerald' },
]

const TAB_COLORS = {
  blue: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  orange: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  teal: 'bg-teal-500/20 text-teal-400 border border-teal-500/30',
  emerald: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
}

export default function OptionsPage({ capital, setCapital }) {
  const [activeTab, setActiveTab] = useState('intraday-live')

  const current = tabs.find(t => t.id === activeTab)

  return (
    <div className="space-y-5">
      {/* Header + Tab bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TrendingUp size={22} className="text-violet-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Options Trading</h2>
            <p className="text-gray-500 text-xs">NIFTY & BANKNIFTY spread strategies with auto regime detection</p>
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
            <span>Start at <span className="text-violet-400 font-semibold">9:50 AM</span></span>
            <span className="text-dark-500">|</span>
            <span>Capital: <span className="text-white">₹25K</span> (paper)</span>
            <span className="text-dark-500">|</span>
            <span>Mode: <span className="text-amber-400">Auto Regime</span> (VIX + PCR + Intraday direction)</span>
            <span className="text-dark-500">|</span>
            <span>Orders from 10:00 AM, auto square-off 3:00 PM</span>
          </>
        ) : (
          <>
            <span>Start at <span className="text-teal-400 font-semibold">9:50 AM</span></span>
            <span className="text-dark-500">|</span>
            <span>Capital: <span className="text-white">₹25K</span> (paper)</span>
            <span className="text-dark-500">|</span>
            <span>Mode: <span className="text-amber-400">Auto Regime</span></span>
            <span className="text-dark-500">|</span>
            <span>Monthly expiry, positions carry overnight</span>
          </>
        )}
      </div>

      {/* Timing Reference */}
      {current?.component === 'intraday' ? (
        <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-dark-600 text-[10px] text-gray-500">
          <span className="text-violet-400 font-semibold">Intraday</span>
          <span className="text-dark-500">|</span>
          <span>Regime: <span className="text-amber-400">Auto every scan</span> (VIX + PCR + Trend → picks strategy)</span>
          <span className="text-dark-500">|</span>
          <span>Scan: <span className="text-violet-400">every 5 min</span></span>
          <span className="text-dark-500">|</span>
          <span>Orders: <span className="text-violet-400">10:00 AM - 2:00 PM</span></span>
          <span className="text-dark-500">|</span>
          <span>Monitor: <span className="text-white">every 15s</span></span>
          <span className="text-dark-500">|</span>
          <span>Square-off: <span className="text-red-400">3:00 PM</span></span>
          <span className="text-dark-500">|</span>
          <span>Positions: <span className="text-white">3/underlying</span></span>
          <span className="text-dark-500">|</span>
          <span>Daily loss: <span className="text-red-400">5% cap</span></span>
          <span className="text-dark-500">|</span>
          <span>Expiry: <span className="text-white">Weekly</span></span>
          <span className="text-dark-500">|</span>
          <span>NIFTY / BANKNIFTY | 6 spread strategies</span>
        </div>
      ) : (
        <div className="flex items-center gap-3 flex-wrap bg-dark-700/50 rounded-lg px-4 py-2 border border-teal-500/10 text-[10px] text-gray-500">
          <span className="text-teal-400 font-semibold">Swing</span>
          <span className="text-dark-500">|</span>
          <span>Regime: <span className="text-amber-400">Auto every scan</span> (VIX + PCR + Trend)</span>
          <span className="text-dark-500">|</span>
          <span>Scan: <span className="text-teal-400">every 4 hours</span></span>
          <span className="text-dark-500">|</span>
          <span>Monitor: <span className="text-white">every 15s</span></span>
          <span className="text-dark-500">|</span>
          <span>Exit: <span className="text-white">SL / Target / 2d before expiry</span></span>
          <span className="text-dark-500">|</span>
          <span>Positions: <span className="text-white">max 2</span></span>
          <span className="text-dark-500">|</span>
          <span>Expiry: <span className="text-white">Monthly</span></span>
          <span className="text-dark-500">|</span>
          <span>NIFTY / BANKNIFTY</span>
        </div>
      )}

      {/* Active component — key forces remount on tab switch */}
      {current?.component === 'intraday' ? (
        <OptionsIntradayTrade key={current.id} mode={current.mode} capital={capital} setCapital={setCapital} />
      ) : (
        <OptionsSwingTrade key={current.id} mode={current.mode} capital={capital} setCapital={setCapital} />
      )}
    </div>
  )
}
