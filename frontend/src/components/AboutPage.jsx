import React from 'react'
import {
  TrendingUp, Shield, Bell, Lock, Server, Zap, Target,
  BarChart3, Clock, AlertTriangle, Sunrise, ArrowRight,
} from 'lucide-react'

const Card = ({ icon: Icon, title, color = 'orange', children }) => (
  <div className="rounded-xl p-5" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
    <div className="flex items-center gap-2 mb-3">
      <Icon size={18} className={`text-${color}-400`} />
      <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
    </div>
    <div className="space-y-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
      {children}
    </div>
  </div>
)

const Row = ({ label, value }) => (
  <div className="flex justify-between py-1" style={{ borderBottom: '1px solid var(--border)' }}>
    <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
    <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
  </div>
)

export default function AboutPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-pink-500 flex items-center justify-center text-white font-bold text-lg">
            IT
          </div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>IntraTrading</h1>
        </div>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Automated Algo Trading Platform — Nifty 500 Stocks on Fyers Broker
        </p>
        <p className="text-xs mt-1" style={{ color: 'var(--accent)' }}>
          Version 4.0 — March 2026
        </p>
      </div>

      {/* Live Engines */}
      <div>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Zap size={18} style={{ color: 'var(--accent)' }} /> Live Engines
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card icon={TrendingUp} title="Equity Intraday" color="green">
            <div className="space-y-0.5">
              <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-500/20 text-green-400 mb-1">PRIORITY 1</span>
              <Row label="Strategies" value="RSI Divergence, BB Contra" />
              <Row label="Capital" value="80% (max ₹80K)" />
              <Row label="Orders" value="10:30 AM - 1:30 PM" />
              <Row label="Square-off" value="3:20 PM" />
              <Row label="Max Positions" value="2 (₹40K each)" />
              <Row label="SL" value="On Fyers exchange (SL-M)" />
              <Row label="VIX-adjusted SL" value="2.0x-3.5x ATR" />
            </div>
          </Card>

          <Card icon={Sunrise} title="BTST — Overnight" color="amber">
            <div className="space-y-0.5">
              <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 mb-1">PRIORITY 2</span>
              <Row label="Timeframes" value="Daily (1d), Hourly (1h)" />
              <Row label="Product" value="CNC (delivery)" />
              <Row label="Entry" value="2:00 PM - 3:15 PM" />
              <Row label="Target" value="+2%" />
              <Row label="Stop Loss" value="-1.5%" />
              <Row label="Max Hold" value="2 trading days" />
              <Row label="Capital" value="Dynamic at 2 PM" />
            </div>
          </Card>

          <Card icon={BarChart3} title="Options Intraday" color="purple">
            <div className="space-y-0.5">
              <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 mb-1">PRIORITY 3</span>
              <Row label="Strategies" value="Bear/Bull spreads" />
              <Row label="Capital" value="Remainder (min ₹15K)" />
              <Row label="Orders" value="10:00 AM - 2:00 PM" />
              <Row label="Square-off" value="3:00 PM" />
              <Row label="Underlyings" value="NIFTY, BANKNIFTY" />
              <Row label="Execution" value="BUY-first (spread margin)" />
              <Row label="Safety" value="Force-close orphaned positions" />
            </div>
          </Card>
        </div>
      </div>

      {/* Risk Management */}
      <Card icon={Shield} title="Risk Management" color="red">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1">
          <Row label="Max Equity Positions" value="2 (₹40K each)" />
          <Row label="Flash Crash Protection" value="Exit at -3% loss" />
          <Row label="VIX SL Tiers" value="Low 2x, Normal 2.5x, High 3x, Extreme 3.5x ATR" />
          <Row label="Trailing SL" value="Breakeven at +1%, Lock 50% at +2%" />
          <Row label="Options Daily Loss Limit" value="5% of capital" />
          <Row label="SL Mandatory" value="Trade cancelled if SL placement fails" />
          <Row label="BTST SL Failure" value="Position auto-exits (no overnight without SL)" />
          <Row label="Spread Margin Check" value="Abort + rollback if SELL leg margin insufficient" />
        </div>
      </Card>

      {/* Capital Allocation */}
      <Card icon={Target} title="Capital Allocation (Priority-Based)" color="blue">
        <div className="space-y-1">
          <Row label="Available < ₹50K" value="100% to Equity" />
          <Row label="Available ₹50K-₹1L" value="Equity 80% → Options remainder (min ₹15K)" />
          <Row label="BTST" value="Dynamic from Fyers at 2 PM (no upfront reservation)" />
          <Row label="Fyers Margin" value="Single pool — real margin checked before each order" />
        </div>
        <p className="text-[10px] mt-2 italic" style={{ color: 'var(--text-secondary)' }}>
          Lesson: Theoretical code-level splits don't work. Fyers has one margin pool. Equity gets priority because it's proven.
        </p>
      </Card>

      {/* Notifications */}
      <Card icon={Bell} title="Telegram Notifications (3-Tier)" color="cyan">
        <div className="space-y-1">
          <div className="flex items-start gap-2">
            <span className="text-[10px] font-bold text-red-400 bg-red-500/20 px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">ALERT</span>
            <span>Flash crash, Fyers disconnect {'>'}2 min, margin warning</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-[10px] font-bold text-orange-400 bg-orange-500/20 px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">TRADE</span>
            <span>Entry, exit, BTST position, breakeven SL move</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-[10px] font-bold text-blue-400 bg-blue-500/20 px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0">SUMMARY</span>
            <span>Morning brief, half-day (1 PM), day-end with Fyers P&L</span>
          </div>
          <Row label="Rate Limited" value="Max 30 msgs per 10 minutes" />
          <Row label="Day-end P&L" value="From Fyers realized (source of truth)" />
        </div>
      </Card>

      {/* Security */}
      <Card icon={Lock} title="Security" color="yellow">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1">
          <Row label="Login" value="Email OTP via Telegram" />
          <Row label="Session" value="JWT (24-hour expiry)" />
          <Row label="API Protection" value="All routes return 401 without token" />
          <Row label="Credentials" value=".env only (never in git)" />
          <Row label="CORS" value="Restricted to known origins" />
          <Row label="Nginx" value="Security headers, .env/.git blocked" />
          <Row label="OTP Rate Limit" value="3 per 10 minutes" />
          <Row label="SEBI Compliance" value="AWS Elastic IP (static, whitelisted)" />
        </div>
      </Card>

      {/* Startup Sequence */}
      <Card icon={Clock} title="Daily Startup Sequence" color="emerald">
        <div className="space-y-1.5">
          {[
            ['9:00 AM', 'Server starts, Fyers TOTP login'],
            ['9:10 AM', 'Stale state files cleaned, regime detected'],
            ['9:15 AM', 'Market opens — live engines start'],
            ['9:30 AM', 'Morning brief → Telegram'],
            ['10:00 AM', 'Options scan begins'],
            ['10:30 AM', 'Equity scan (15m candle close)'],
            ['1:00 PM', 'Half-day summary → Telegram'],
            ['1:50 PM', 'BTST engine starts'],
            ['3:00 PM', 'Options square-off + force-close'],
            ['3:20 PM', 'Equity square-off'],
            ['3:45 PM', 'Day-end Fyers P&L → Telegram, server shutdown'],
          ].map(([time, event]) => (
            <div key={time} className="flex items-center gap-3">
              <span className="text-[10px] font-mono w-16 flex-shrink-0" style={{ color: 'var(--accent)' }}>{time}</span>
              <ArrowRight size={10} style={{ color: 'var(--text-secondary)' }} />
              <span>{event}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Tech Stack */}
      <Card icon={Server} title="Tech Stack" color="gray">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1">
          <Row label="Backend" value="FastAPI + Python 3.12" />
          <Row label="Frontend" value="React + Vite + Tailwind CSS" />
          <Row label="Broker" value="Fyers API v3 (TOTP auto-login)" />
          <Row label="Data" value="yfinance + Fyers LTP" />
          <Row label="Hosting" value="AWS EC2 Mumbai (ap-south-1)" />
          <Row label="Static IP" value="Elastic IP (SEBI compliant)" />
          <Row label="Deploy" value="GitHub → git pull → systemd restart" />
          <Row label="Auth" value="JWT + Email OTP via Telegram" />
        </div>
      </Card>

      {/* Active Strategies */}
      <Card icon={AlertTriangle} title="Active Strategies" color="orange">
        <div className="space-y-2">
          <div>
            <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>play8_rsi_divergence</span>
            <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">PRIMARY</span>
            <p className="mt-0.5">RSI divergence reversal — detects price/RSI divergence for counter-trend entries. Leads 93% of regime configurations. Best performer: +₹152/trade expectancy.</p>
          </div>
          <div>
            <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>play6_bb_contra</span>
            <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">SECONDARY</span>
            <p className="mt-0.5">Bollinger Band mean reversion — buys at lower band, sells at upper band with 200 SMA trend filter.</p>
          </div>
          <div>
            <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>play4_supertrend</span>
            <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400">LOW VIX ONLY</span>
            <p className="mt-0.5">Supertrend Power Trend — only when VIX {'<'} 18. Removed from high-volatility regimes.</p>
          </div>
          <div>
            <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>play10_momentum_rank</span>
            <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">DISABLED</span>
            <p className="mt-0.5">Disabled — 0% win rate. Will re-evaluate when market conditions change.</p>
          </div>
        </div>
      </Card>

      {/* Footer */}
      <div className="text-center py-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>Built with Claude AI — Fund Manager, Strategist, Engineer, QA, Security, Risk Manager, Operations</p>
        <p className="mt-1" style={{ color: 'var(--accent)' }}>Goal: ₹1L → ₹20Cr by Dec 2035</p>
      </div>
    </div>
  )
}
