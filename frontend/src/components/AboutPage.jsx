import React, { useState, useEffect } from 'react'
import {
  Zap,
  Target,
  Sunrise,
  BarChart3,
  Shield,
  Bell,
  Lock,
  Code2,
  PieChart,
} from 'lucide-react'
import { getAuthToken } from '../services/api/base'

function Section({ icon: Icon, title, color, children }) {
  return (
    <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
      <h2 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <Icon size={16} className={color} />
        {title}
      </h2>
      {children}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between py-1 border-b border-dark-600 last:border-0">
      <span className="text-gray-500 text-xs">{label}</span>
      <span className="text-white text-xs font-medium">{value}</span>
    </div>
  )
}

function Bullet({ children, color = 'text-gray-500' }) {
  return (
    <li className="flex items-start gap-2 text-xs text-gray-400 leading-relaxed">
      <span className={`mt-0.5 ${color}`}>&#9679;</span>
      <span>{children}</span>
    </li>
  )
}

function CapitalAllocationLive() {
  const [data, setData] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const token = getAuthToken()
        const headers = token ? { Authorization: `Bearer ${token}` } : {}
        const API = ''
        const [funds, eqStatus, optStatus, btstStatus, regime] = await Promise.all([
          fetch(`${API}/api/fyers/funds`, { headers }).then(r => r.json()).catch(() => null),
          fetch(`${API}/api/auto/status`, { headers }).then(r => r.json()).catch(() => null),
          fetch(`${API}/api/options/auto/status`, { headers }).then(r => r.json()).catch(() => null),
          fetch(`${API}/api/btst/status`, { headers }).then(r => r.json()).catch(() => null),
          fetch(`${API}/api/equity/regime`, { headers }).then(r => r.json()).catch(() => null),
        ])
        let available = 0
        for (const f of (funds?.fund_limit || [])) {
          if (f.id === 10) available = f.equityAmount || 0
        }
        setData({
          available,
          eqCapital: eqStatus?.capital || 0,
          eqRunning: eqStatus?.is_running || false,
          eqStrategies: eqStatus?.strategies?.length || 0,
          optCapital: optStatus?.capital || 0,
          optRunning: optStatus?.is_running || false,
          btstCapital: btstStatus?.capital || 0,
          btstRunning: btstStatus?.is_running || false,
          vix: regime?.components?.vix || 0,
          regime: regime?.regime || '?',
        })
      } catch {}
    }
    load()
    const id = setInterval(load, 60000)
    return () => clearInterval(id)
  }, [])

  if (!data) return null

  const total = data.eqCapital + data.optCapital + data.btstCapital
  const eqPct = total > 0 ? Math.round(data.eqCapital * 100 / total) : 0
  const optPct = total > 0 ? Math.round(data.optCapital * 100 / total) : 0
  const btstPct = total > 0 ? Math.round(data.btstCapital * 100 / total) : 0

  return (
    <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
      <h2 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <PieChart size={16} className="text-cyan-400" />
        Capital Allocation (Live)
        <span className="text-[9px] bg-dark-600 text-gray-400 px-2 py-0.5 rounded ml-auto">
          VIX {data.vix} | {data.regime.replace(/_/g, ' ')}
        </span>
      </h2>

      {/* Allocation bar */}
      <div className="flex h-4 rounded-full overflow-hidden mb-3 border border-dark-500">
        {data.optCapital > 0 && (
          <div className="bg-violet-500 flex items-center justify-center" style={{ width: `${optPct}%` }}>
            <span className="text-[8px] text-white font-bold">{optPct}%</span>
          </div>
        )}
        {data.eqCapital > 0 && (
          <div className="bg-green-500 flex items-center justify-center" style={{ width: `${eqPct}%` }}>
            <span className="text-[8px] text-white font-bold">{eqPct}%</span>
          </div>
        )}
        {data.btstCapital > 0 && (
          <div className="bg-amber-500 flex items-center justify-center" style={{ width: `${btstPct}%` }}>
            <span className="text-[8px] text-white font-bold">{btstPct}%</span>
          </div>
        )}
        {total === 0 && (
          <div className="bg-gray-600 w-full flex items-center justify-center">
            <span className="text-[8px] text-gray-300">Market closed</span>
          </div>
        )}
      </div>

      {/* Engine details */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-dark-800/50 rounded-lg p-3 border border-dark-600">
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-2.5 h-2.5 rounded-full bg-violet-500"></div>
            <span className="text-[10px] text-violet-400 font-semibold">OPTIONS</span>
            {data.optRunning && <span className="text-[8px] text-green-400 ml-auto">● LIVE</span>}
          </div>
          <p className="text-sm font-bold text-white">₹{(data.optCapital || 0).toLocaleString('en-IN')}</p>
        </div>
        <div className="bg-dark-800/50 rounded-lg p-3 border border-dark-600">
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
            <span className="text-[10px] text-green-400 font-semibold">EQUITY</span>
            {data.eqRunning && <span className="text-[8px] text-green-400 ml-auto">● LIVE</span>}
          </div>
          <p className="text-sm font-bold text-white">₹{(data.eqCapital || 0).toLocaleString('en-IN')}</p>
          <p className="text-[9px] text-gray-500">{data.eqStrategies} strategies</p>
        </div>
        <div className="bg-dark-800/50 rounded-lg p-3 border border-dark-600">
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500"></div>
            <span className="text-[10px] text-amber-400 font-semibold">BTST</span>
            {data.btstRunning && <span className="text-[8px] text-green-400 ml-auto">● LIVE</span>}
          </div>
          <p className="text-sm font-bold text-white">₹{(data.btstCapital || 0).toLocaleString('en-IN')}</p>
        </div>
      </div>

      {/* Logic explanation */}
      <div className="mt-3 text-[10px] text-gray-500 space-y-0.5">
        <p>&#9679; Allocation based on rolling 3-day P&L — winner gets more capital</p>
        <p>&#9679; VIX {'>'} 22: options boosted +10% (higher premiums). VIX {'<'} 15: equity boosted +10%</p>
        <p>&#9679; Both engines losing: 20% cash reserve held back</p>
        <p>&#9679; Available: ₹{(data.available || 0).toLocaleString('en-IN')} from Fyers</p>
      </div>
    </div>
  )
}

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-4 pb-12">
      {/* System Overview */}
      <div className="bg-gradient-to-br from-orange-500/10 via-dark-700 to-pink-500/10 rounded-2xl border border-dark-500 p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-pink-500 flex items-center justify-center text-white font-bold text-base flex-shrink-0">
            IT
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">IntraTrading</h1>
            <p className="text-xs text-gray-500">Automated Algo Trading Platform</p>
          </div>
        </div>
        <p className="text-sm text-gray-400 leading-relaxed mt-2">
          Scans Nifty 500 stocks using technical strategies. Executes trades on Fyers broker.
        </p>
        <div className="flex gap-2 mt-3">
          {['Equity Intraday', 'Options Intraday', 'BTST'].map((e) => (
            <span key={e} className="px-2.5 py-1 rounded-lg bg-dark-600 border border-dark-500 text-xs text-orange-400 font-medium">
              {e}
            </span>
          ))}
        </div>
      </div>

      {/* Live Engines */}
      <Section icon={Zap} title="Live Engines" color="text-orange-400">
        <div className="space-y-4">
          {/* Options Intraday — PRIMARY */}
          <div className="bg-dark-800/50 rounded-lg p-4 border border-dark-600">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 size={14} className="text-violet-400" />
              <h3 className="text-xs font-semibold text-violet-400 uppercase tracking-wide">
                Options Intraday
              </h3>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-400 font-bold">PRIMARY</span>
            </div>
            <ul className="space-y-1.5">
              <Bullet color="text-violet-400">Strategies: Bear call/put spreads, Bull put/call spreads</Bullet>
              <Bullet color="text-violet-400">Capital: 50% of available (max ₹50K) — proven ₹795/trade on paper</Bullet>
              <Bullet color="text-violet-400">BUY legs placed first → spread margin ~₹20K (not ₹1.13L naked)</Bullet>
              <Bullet color="text-violet-400">Orders 10:00 AM - 2:00 PM, square-off 3:00 PM</Bullet>
              <Bullet color="text-violet-400">Underlyings: NIFTY, BANKNIFTY</Bullet>
              <Bullet color="text-violet-400">Force-close safety net on orphaned positions</Bullet>
            </ul>
          </div>

          {/* Equity Intraday */}
          <div className="bg-dark-800/50 rounded-lg p-4 border border-dark-600">
            <div className="flex items-center gap-2 mb-2">
              <Target size={14} className="text-green-400" />
              <h3 className="text-xs font-semibold text-green-400 uppercase tracking-wide">
                Equity Intraday
              </h3>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 font-bold">SECONDARY</span>
            </div>
            <ul className="space-y-1.5">
              <Bullet color="text-green-400">9 strategies — regime picks dynamically based on market conditions</Bullet>
              <Bullet color="text-green-400">Capital: 50% of available (remainder after Options)</Bullet>
              <Bullet color="text-green-400">Orders 10:30 AM - 1:30 PM, square-off 3:20 PM</Bullet>
              <Bullet color="text-green-400">Max 2 positions, SL mandatory on Fyers exchange</Bullet>
              <Bullet color="text-green-400">VIX-adjusted SL: 2.0x - 3.5x ATR (4 tiers)</Bullet>
              <Bullet color="text-green-400">SL failure → trade cancelled + emergency exit</Bullet>
            </ul>
          </div>

          {/* BTST */}
          <div className="bg-dark-800/50 rounded-lg p-4 border border-dark-600">
            <div className="flex items-center gap-2 mb-2">
              <Sunrise size={14} className="text-amber-400" />
              <h3 className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
                BTST — Buy Today Sell Tomorrow
              </h3>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold">DYNAMIC</span>
            </div>
            <ul className="space-y-1.5">
              <Bullet color="text-amber-400">Uses daily (1d) and hourly (1h) timeframes</Bullet>
              <Bullet color="text-amber-400">Product: CNC (delivery), carries overnight</Bullet>
              <Bullet color="text-amber-400">Entry: 2:00 PM - 3:15 PM</Bullet>
              <Bullet color="text-amber-400">Target: +2%, SL: -1.5%, max hold: 2 days</Bullet>
              <Bullet color="text-amber-400">Dynamic capital from Fyers at 2 PM</Bullet>
              <Bullet color="text-amber-400">SL failure → position exits immediately (no overnight without SL)</Bullet>
            </ul>
          </div>
        </div>
      </Section>

      {/* Dynamic Capital Allocation — LIVE from API */}
      <CapitalAllocationLive />

      {/* Risk Management */}
      <Section icon={Shield} title="Risk Management" color="text-red-400">
        <ul className="space-y-1.5">
          <Bullet color="text-red-400">Max 2 equity positions (₹40K each)</Bullet>
          <Bullet color="text-red-400">Flash crash protection: exit at -3%</Bullet>
          <Bullet color="text-red-400">VIX-adjusted stop loss (4 tiers)</Bullet>
          <Bullet color="text-red-400">Trailing SL: breakeven at +1%, lock 50% at +2%</Bullet>
          <Bullet color="text-red-400">Daily loss limit: 5% for options</Bullet>
          <Bullet color="text-red-400">SL mandatory -- trade cancelled if SL placement fails</Bullet>
        </ul>
      </Section>

      {/* Notifications */}
      <Section icon={Bell} title="Notifications (Telegram)" color="text-blue-400">
        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <span className="text-[10px] font-bold text-red-400 bg-red-500/20 px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">ALERT</span>
            <p className="text-xs text-gray-400">Flash crash, Fyers disconnect &gt;2min, margin warning</p>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-[10px] font-bold text-orange-400 bg-orange-500/20 px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">TRADE</span>
            <p className="text-xs text-gray-400">Entry, exit, BTST position, breakeven SL</p>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-[10px] font-bold text-blue-400 bg-blue-500/20 px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">SUMMARY</span>
            <p className="text-xs text-gray-400">Morning brief, half-day, day-end with Fyers P&L</p>
          </div>
          <p className="text-[10px] text-gray-600 mt-2">Rate limited: max 30 messages per 10 minutes</p>
        </div>
      </Section>

      {/* Security */}
      <Section icon={Lock} title="Security" color="text-emerald-400">
        <ul className="space-y-1.5">
          <Bullet color="text-emerald-400">OTP login via Telegram (JWT 24h session)</Bullet>
          <Bullet color="text-emerald-400">All API routes protected (401 without token)</Bullet>
          <Bullet color="text-emerald-400">Credentials in .env only (never in git)</Bullet>
          <Bullet color="text-emerald-400">CORS restricted to known origins</Bullet>
          <Bullet color="text-emerald-400">Nginx security headers on cloud</Bullet>
        </ul>
      </Section>

      {/* Tech Stack */}
      <Section icon={Code2} title="Tech Stack" color="text-cyan-400">
        <div className="grid grid-cols-2 gap-x-6 gap-y-1">
          {[
            ['Backend', 'FastAPI + Python 3.12'],
            ['Frontend', 'React + Vite + Tailwind CSS'],
            ['Broker', 'Fyers API v3 (TOTP auto-login)'],
            ['Data', 'yfinance (charts) + Fyers (live LTP)'],
            ['Hosting', 'AWS EC2 Mumbai (Elastic IP)'],
            ['Notifications', 'Telegram Bot API'],
          ].map(([label, value]) => (
            <div key={label} className="flex items-baseline gap-2 text-xs py-0.5">
              <span className="text-gray-500 font-medium w-24 flex-shrink-0">{label}</span>
              <span className="text-gray-400">{value}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* Footer */}
      <p className="text-center text-[10px] text-gray-600 pt-2">
        IntraTrading v4.0 &mdash; Built for consistent compounding
      </p>
    </div>
  )
}
