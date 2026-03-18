import React, { useState } from 'react'
import {
  TrendingUp,
  Shield,
  Zap,
  Target,
  Clock,
  BarChart3,
  Eye,
  Play,
  Square,
  ArrowRight,
  Monitor,
  Repeat,
  Settings,
  IndianRupee,
  CheckCircle2,
  Search,
  ShoppingCart,
  LineChart,
  AlertTriangle,
  Info,
  BookOpen,
  Layers,
  CalendarDays,
} from 'lucide-react'

const tabs = [
  { id: 'overview', label: 'Overview', icon: Info },
  { id: 'how-it-works', label: 'How It Works', icon: Layers },
  { id: 'get-started', label: 'Getting Started', icon: Play },
  { id: 'trading-day', label: 'Trading Day', icon: CalendarDays },
  { id: 'strategies', label: 'Strategies', icon: Target },
  { id: 'options', label: 'Options Trading', icon: BarChart3 },
  { id: 'futures', label: 'Futures Trading', icon: TrendingUp },
  { id: 'pages', label: 'App Pages', icon: BookOpen },
  { id: 'rules', label: 'Rules & Notes', icon: Shield },
]

/* ─── Tab: Overview ─── */
function OverviewTab() {
  return (
    <>
      <div className="bg-gradient-to-br from-orange-500/10 via-dark-700 to-pink-500/10 rounded-2xl border border-dark-500 p-8 mb-6">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-orange-500 to-pink-500 flex items-center justify-center text-white font-bold text-2xl flex-shrink-0">
            IT
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">IntraTrading</h1>
            <p className="text-gray-400 leading-relaxed">
              An automated stock trading system for the <span className="text-white font-medium">Indian market (NSE)</span>.
              It scans <span className="text-white font-medium">Nifty 500 stocks</span> using 6 proven technical strategies,
              finds high-probability trade setups, and automatically places orders through your
              <span className="text-white font-medium"> Fyers broker account</span> — with stop-loss and target built in.
              Supports <span className="text-orange-400 font-medium">equity intraday</span>,
              <span className="text-emerald-400 font-medium"> swing trading</span>,
              <span className="text-violet-400 font-medium"> NIFTY/BANKNIFTY options spreads</span>, and
              <span className="text-amber-400 font-medium"> NSE F&O stock futures</span> with OI sentiment analysis.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
          <Search size={20} className="text-blue-400 mb-3" />
          <h3 className="text-sm font-semibold text-white mb-1">Scan</h3>
          <p className="text-xs text-gray-400 leading-relaxed">Scans all Nifty 500 stocks using 6 technical strategies to find buy/sell signals with clear entry, stop-loss, and target.</p>
        </div>
        <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
          <ShoppingCart size={20} className="text-green-400 mb-3" />
          <h3 className="text-sm font-semibold text-white mb-1">Trade</h3>
          <p className="text-xs text-gray-400 leading-relaxed">Automatically places orders on Fyers with built-in SL & target. Risks only 2% of your capital per trade. No manual intervention needed.</p>
        </div>
        <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
          <LineChart size={20} className="text-purple-400 mb-3" />
          <h3 className="text-sm font-semibold text-white mb-1">Track</h3>
          <p className="text-xs text-gray-400 leading-relaxed">Tracks every trade with P&L, charges, win rate, and strategy performance. Daily P&L charts and full trade history with filters.</p>
        </div>
      </div>
    </>
  )
}

/* ─── Tab: How It Works ─── */
function HowItWorksTab() {
  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">How It Works</h2>
      <p className="text-xs text-gray-500 mb-6">The automated trading loop — on-demand scans that fill slots as they open</p>

      <div className="flex items-center justify-between gap-2 mb-8 bg-dark-700 rounded-2xl border border-dark-500 p-6">
        {[
          { icon: Search, label: 'Scan 500 Stocks', color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
          { icon: Target, label: 'Find Signals', color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
          { icon: Shield, label: 'Check Risk', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20' },
          { icon: ShoppingCart, label: 'Place Order', color: 'text-green-400 bg-green-500/10 border-green-500/20' },
          { icon: Eye, label: 'Monitor P&L', color: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
        ].map((step, i) => (
          <React.Fragment key={i}>
            <div className="flex flex-col items-center gap-2 flex-1">
              <div className={`w-14 h-14 rounded-xl border flex items-center justify-center ${step.color}`}>
                <step.icon size={22} />
              </div>
              <span className="text-[10px] text-gray-400 text-center font-medium">{step.label}</span>
            </div>
            {i < 4 && <ArrowRight size={14} className="text-dark-400 flex-shrink-0 mt-[-16px]" />}
          </React.Fragment>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-dark-700 rounded-xl p-5 border border-dark-500">
          <h3 className="text-sm font-semibold text-orange-400 mb-3 flex items-center gap-2">
            <Zap size={14} /> Intraday Mode
          </h3>
          <ul className="space-y-2 text-xs text-gray-400">
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>On-demand scan: initial scan at 12:00 PM, re-scans when a slot opens</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Places entry + SL orders on Fyers, monitors target every 60s</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Max 4 positions (live) / 10 positions (paper)</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Orders: 12:00 PM - 2:00 PM. Square-off at 3:15 PM</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Uses 5m / 15m candle timeframes</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>All 6 strategies available. Price filter: Rs 50 - Rs 5,000</li>
          </ul>
        </div>
        <div className="bg-dark-700 rounded-xl p-5 border border-emerald-500/20">
          <h3 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
            <Repeat size={14} /> Swing Mode
          </h3>
          <ul className="space-y-2 text-xs text-gray-400">
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Morning scan at 9:20 AM. Retries every 30 min until 2 PM if slot open</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>BUY only — CNC (delivery) does not support short selling</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Max 1 position (live) / 5 positions (paper)</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Orders re-placed daily (CNC orders expire each day)</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Uses 1d candle timeframe. 4 strategies: Play #1, #2, #5, #6</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Price filter: Rs 100 - Rs 1,500 only</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Nifty 50 SMA filter: blocks BUY only when Nifty is below 50-day SMA (genuine weakness). Normal red days in an uptrend are allowed</li>
          </ul>
        </div>
      </div>
    </>
  )
}

/* ─── Tab: Getting Started ─── */
function GetStartedTab() {
  const steps = [
    {
      step: '1', title: 'Connect Your Broker', icon: Settings,
      desc: 'Click "Login to Fyers" on the Dashboard sidebar. This connects your Fyers account for placing orders and fetching live prices. You need a Fyers account with API access (get credentials from myapi.fyers.in).',
      color: 'from-blue-500/20 to-blue-500/5 border-blue-500/30',
    },
    {
      step: '2', title: 'Set Your Capital', icon: IndianRupee,
      desc: 'Enter how much money you want to trade with (e.g. Rs 50,000 or Rs 1,00,000). The system will risk only 2% per trade. Example: with Rs 1L capital, max risk per trade = Rs 2,000.',
      color: 'from-green-500/20 to-green-500/5 border-green-500/30',
    },
    {
      step: '3', title: 'Start with Paper Trading', icon: Monitor,
      desc: 'Go to "Paper Trade" tab and start paper trading first. It uses the exact same strategies and logic but with virtual money — no real orders are placed. Perfect for testing before going live.',
      color: 'from-purple-500/20 to-purple-500/5 border-purple-500/30',
    },
    {
      step: '4', title: 'Go Live', icon: Play,
      desc: 'Once confident with paper results, switch to Live mode using the toggle on the Intraday or Swing page. The system will scan at 12 PM (intraday) or 9:20 AM (swing), place real orders, manage SL/target, and square off — all automatically.',
      color: 'from-orange-500/20 to-orange-500/5 border-orange-500/30',
    },
    {
      step: '5', title: 'Review Your Trades', icon: BarChart3,
      desc: 'Each trading page shows Daily Strategy Performance — which strategy worked each day with per-trade detail. Trade Log has full history with charges. Dashboard shows all 4 engines, win rate, and best/worst strategies.',
      color: 'from-cyan-500/20 to-cyan-500/5 border-cyan-500/30',
    },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">Getting Started</h2>
      <p className="text-xs text-gray-500 mb-6">Step-by-step guide to start trading</p>

      <div className="space-y-4">
        {steps.map((w, i) => (
          <div key={i} className={`flex items-start gap-4 bg-gradient-to-r ${w.color} rounded-xl border p-5`}>
            <div className="w-10 h-10 rounded-lg bg-dark-700/80 flex items-center justify-center text-orange-400 font-bold text-base flex-shrink-0">
              {w.step}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <w.icon size={14} className="text-gray-400" />
                <h3 className="text-sm font-semibold text-white">{w.title}</h3>
              </div>
              <p className="text-xs text-gray-400 leading-relaxed">{w.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

/* ─── Tab: Trading Day ─── */
function TradingDayTab() {
  const timeline = [
    { time: '9:15 AM', title: 'Market Opens', desc: 'Start intraday engine (Live or Paper). Swing engine scans at 9:20 AM for overnight signals. Intraday waits until 12:00 PM before placing orders.', color: 'bg-green-500', textColor: 'text-green-400', highlight: true },
    { time: '9:20 AM', title: 'Swing Morning Scan', desc: "Swing trader scans all 4 strategies on daily candles. If no signal found and slot open, retries every 30 min until 2 PM. BUY signals only.", color: 'bg-emerald-500', textColor: 'text-emerald-400' },
    { time: '12:00 PM', title: 'Intraday Orders Begin', desc: 'Initial full scan runs to fill all position slots. On-demand mode: re-scans immediately when a slot opens (position hits SL or target).', color: 'bg-orange-500', textColor: 'text-orange-400', highlight: true },
    { time: '12:00 - 2:00 PM', title: 'Active Trading', desc: 'Monitors positions every 60s. When a trade closes (SL/target), scans again to fill the slot. Max 4 live / 10 paper positions.', color: 'bg-orange-500', textColor: 'text-orange-400' },
    { time: '2:00 PM', title: 'Order Cutoff', desc: 'No new intraday or swing orders after this time. Existing positions keep running with their SL/target.', color: 'bg-yellow-500', textColor: 'text-yellow-400' },
    { time: '2:00 - 3:15 PM', title: 'Position Monitoring', desc: 'Intraday engine monitors open positions. Trades can still hit target or SL. No new scans or orders.', color: 'bg-blue-500', textColor: 'text-blue-400' },
    { time: '3:15 PM', title: 'Intraday Square-Off', desc: 'All remaining intraday positions closed at market price. Swing positions carry overnight (CNC delivery).', color: 'bg-red-500', textColor: 'text-red-400', highlight: true },
    { time: 'After 3:30 PM', title: 'Review & Learn', desc: "Check Trade Log, Daily P&L, and Dashboard for the day's results. Daily Strategy Performance shows per-strategy breakdown on each trading page.", color: 'bg-purple-500', textColor: 'text-purple-400' },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">A Typical Trading Day</h2>
      <p className="text-xs text-gray-500 mb-6">What happens automatically once you press Start</p>

      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6">
        <div className="relative">
          <div className="absolute left-[18px] top-4 bottom-4 w-px bg-dark-500" />
          <div className="space-y-5">
            {timeline.map((item, i) => (
              <div key={i} className="flex items-start gap-4 relative">
                <div className={`w-[10px] h-[10px] rounded-full ${item.color} flex-shrink-0 mt-1.5 z-10 ${item.highlight ? 'ring-4 ring-opacity-20 ring-current' : ''}`} />
                <div className={`flex-1 ${item.highlight ? 'bg-dark-600/50 rounded-xl p-3 -m-3 border border-dark-500' : ''}`}>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-xs font-bold ${item.textColor}`}>{item.time}</span>
                    <span className="text-xs text-gray-600">{'\u2014'}</span>
                    <span className="text-sm font-semibold text-white">{item.title}</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}

/* ─── Tab: Strategies ─── */
function StrategiesTab() {
  const strategies = [
    {
      num: '#1', name: 'EMA-EMA Crossover', type: 'Trend Following',
      indicators: '9 EMA, 21 EMA, 50 SMA',
      how: '9 EMA crosses above 21 EMA (BUY) or below (SELL). 50 SMA confirms broad trend. For swing: additional filters — market regime, ADX > 25, EMA gap quality, SMA50 slope & distance.',
      exit: 'Opposite crossover or 1:2 risk-reward target.',
      sl: 'Swing: 1.5x ATR. Intraday: wider of swing low and ATR.',
      rr: '1:2',
      intraday: { timeframes: ['5m', '15m'], best: '15m', note: '15m gives cleaner signals with less noise. 5m gives more signals but more whipsaws.' },
      swing: { timeframes: ['1h', '1d'], best: '1d', note: 'Daily candles capture multi-day trend shifts. 6 swing filters active (ADX, market regime, EMA gap, SMA50 slope/distance). BUY only.' },
      color: 'border-blue-500/20', badge: 'text-blue-400 bg-blue-500/15',
    },
    {
      num: '#2', name: 'Triple MA Trend Filter', type: 'Trend Following',
      indicators: '20 EMA, 50 SMA, 200 SMA',
      how: 'Three MAs stacked in order (20 > 50 > 200 for BUY). Trades pullbacks to 20/50 zone with reversal confirmation.',
      exit: '20 EMA crosses 50 SMA opposite, or 1:2 target.',
      sl: 'Beyond the swing extreme of the pullback.',
      rr: '1:2',
      intraday: { timeframes: ['15m'], best: '15m', note: '15m only — needs 200 SMA history. Higher win rate but fewer signals. Best in strong trending markets.' },
      swing: { timeframes: ['1h', '1d'], best: '1d', note: 'Daily triple MA alignment captures strong multi-week trends. BUY only in swing.' },
      color: 'border-purple-500/20', badge: 'text-purple-400 bg-purple-500/15',
    },
    {
      num: '#3', name: 'VWAP Intraday Pullback', type: 'Intraday Precision',
      indicators: 'Session VWAP',
      how: 'Price trending above/below VWAP, pulls back to VWAP, then bounces with reversal candle. Pure intraday — VWAP resets each session.',
      exit: 'Last swing extreme or 1:2 risk-reward.',
      sl: 'Beyond the pullback extreme or VWAP zone.',
      rr: '1:2',
      intraday: { timeframes: ['5m'], best: '5m', note: '5m only. Works best 9:30 AM - 2:30 PM in clear trending sessions. Avoid last hour before close.' },
      swing: null,
      color: 'border-cyan-500/20', badge: 'text-cyan-400 bg-cyan-500/15',
    },
    {
      num: '#4', name: 'Supertrend Power Trend', type: 'Intraday Precision',
      indicators: 'Supertrend (ATR 10, Mult 3), 20 EMA',
      how: 'Supertrend confirms direction, 20 EMA creates a "Power Zone". Trades pullbacks into this zone with trigger candle.',
      exit: 'Recent swing extreme or 1:2 to 1:3 target.',
      sl: 'Beyond the trigger candle extreme. Tightest stops.',
      rr: '1:2 to 1:3',
      intraday: { timeframes: ['5m', '15m'], best: '5m', note: '5m recommended for tighter entries. 15m gives fewer but higher quality signals. Mechanical, tight entries with Power Zone.' },
      swing: null,
      color: 'border-orange-500/20', badge: 'text-orange-400 bg-orange-500/15',
    },
    {
      num: '#5', name: 'BB Squeeze Breakout', type: 'Volatility Expansion',
      indicators: 'Bollinger Bands (20, 2)',
      how: 'Bands squeeze tight (low volatility), then price breaks out with a strong candle closing beyond the band. Next candle confirms.',
      exit: '1:1.5 risk-reward (primary), 1:2 (secondary).',
      sl: 'Middle Band (20 SMA).',
      rr: '1:1.5',
      intraday: { timeframes: ['15m'], best: '15m', note: '15m gives enough candles to detect squeeze. Best after sideways morning sessions — catches afternoon breakouts.' },
      swing: { timeframes: ['1d'], best: '1d', note: 'Daily BB squeeze = multi-day consolidation ready to breakout. Strong momentum plays. BUY only in swing.' },
      color: 'border-green-500/20', badge: 'text-green-400 bg-green-500/15',
    },
    {
      num: '#6', name: 'BB Contra Mean Reversion', type: 'Mean Reversion',
      indicators: 'Bollinger Bands (20, 2), 200 SMA',
      how: 'Price touches outer band in a confirmed trend (200 SMA direction) and shows reversal candle. Bets on reversion to the mean.',
      exit: 'Middle Band (20 SMA) — mean reversion target.',
      sl: 'Beyond the reversal candle extreme.',
      rr: '1:1 to 1:2',
      intraday: { timeframes: ['5m', '15m'], best: '15m', note: '15m recommended for cleaner signals. 5m gives quicker entries but needs more precision. Conservative, selective strategy.' },
      swing: { timeframes: ['1d'], best: '1d', note: 'Daily mean reversion from lower band in uptrends offers high-probability swing entries. BUY only in swing.' },
      color: 'border-pink-500/20', badge: 'text-pink-400 bg-pink-500/15',
    },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">6 Trading Strategies</h2>
      <p className="text-xs text-gray-500 mb-6">From a proven Technical Indicator Playbook — each uses different indicators and market conditions</p>

      <div className="space-y-4">
        {strategies.map((s, i) => (
          <div key={i} className={`bg-dark-700 rounded-xl border ${s.color} p-5`}>
            <div className="flex items-center gap-2 mb-3">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${s.badge}`}>{s.num}</span>
              <span className="text-base font-semibold text-white">{s.name}</span>
              <span className="text-[9px] text-gray-500 bg-dark-600 px-2 py-0.5 rounded ml-1">{s.type}</span>
              <div className="flex-1" />
              <span className="text-[10px] font-mono text-gray-400">R:R {s.rr}</span>
            </div>

            {/* Entry / Exit / Indicators */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 mb-3">
              <div>
                <p className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider mb-0.5">Indicators</p>
                <p className="text-xs text-gray-300">{s.indicators}</p>
              </div>
              <div>
                <p className="text-[9px] font-semibold text-red-400/70 uppercase tracking-wider mb-0.5">Exit & Stop-Loss</p>
                <p className="text-xs text-gray-400 leading-relaxed">{s.exit} SL: {s.sl}</p>
              </div>
              <div className="col-span-2">
                <p className="text-[9px] font-semibold text-green-400/70 uppercase tracking-wider mb-0.5">Entry</p>
                <p className="text-xs text-gray-400 leading-relaxed">{s.how}</p>
              </div>
            </div>

            {/* Intraday & Swing timeframe details */}
            <div className={`grid ${s.swing ? 'grid-cols-2' : 'grid-cols-1'} gap-3 pt-3 border-t border-dark-600`}>
              {/* Intraday */}
              <div className="bg-dark-600/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <Zap size={10} className="text-orange-400" />
                  <span className="text-[10px] font-semibold text-orange-400">Intraday</span>
                </div>
                <div className="flex gap-1 mb-1.5">
                  {s.intraday.timeframes.map(tf => (
                    <span key={tf} className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${
                      tf === s.intraday.best
                        ? 'bg-orange-500/20 text-orange-400 ring-1 ring-orange-500/30'
                        : 'bg-dark-700 text-gray-500'
                    }`}>
                      {tf} {tf === s.intraday.best ? '\u2605' : ''}
                    </span>
                  ))}
                </div>
                <p className="text-[10px] text-gray-500 leading-relaxed">{s.intraday.note}</p>
              </div>

              {/* Swing */}
              {s.swing ? (
                <div className="bg-dark-600/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Repeat size={10} className="text-emerald-400" />
                    <span className="text-[10px] font-semibold text-emerald-400">Swing</span>
                  </div>
                  <div className="flex gap-1 mb-1.5">
                    {s.swing.timeframes.map(tf => (
                      <span key={tf} className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${
                        tf === s.swing.best
                          ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30'
                          : 'bg-dark-700 text-gray-500'
                      }`}>
                        {tf} {tf === s.swing.best ? '\u2605' : ''}
                      </span>
                    ))}
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">{s.swing.note}</p>
                </div>
              ) : (
                <div className="bg-dark-600/30 rounded-lg p-3 flex items-center justify-center">
                  <span className="text-[10px] text-gray-600 italic">Not available for swing — intraday only</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

/* ─── Tab: Options Trading ─── */
function OptionsTab() {
  const spreads = [
    {
      name: 'Bull Call Spread', type: 'Debit', conviction: 'Strongly Bullish', winRate: '~55%',
      legs: 'Buy lower CE + Sell higher CE',
      payoff: 'Max Profit = (Strike Width - Net Debit) x Lot Size\nMax Loss = Net Debit x Lot Size',
      desc: 'Buy an ATM Call and sell an OTM Call. Profits when the market moves up strongly past the long strike. Limited risk (net debit paid).',
      color: 'border-green-500/20', badge: 'text-green-400 bg-green-500/15',
    },
    {
      name: 'Bull Put Spread', type: 'Credit', conviction: 'Mildly Bullish', winRate: '~65-70%',
      legs: 'Sell higher PE + Buy lower PE',
      payoff: 'Max Profit = Net Credit x Lot Size\nMax Loss = (Strike Width - Net Credit) x Lot Size',
      desc: 'Sell an OTM Put and buy a further OTM Put for protection. Profits from time decay when market stays above the sold strike. High probability — the market just needs to not fall.',
      color: 'border-emerald-500/20', badge: 'text-emerald-400 bg-emerald-500/15',
      highProb: true,
    },
    {
      name: 'Iron Condor', type: 'Credit', conviction: 'Neutral / Range-bound', winRate: '~65-70%',
      legs: 'Bull Put Spread + Bear Call Spread (4 legs)',
      payoff: 'Max Profit = Total Net Credit x Lot Size\nMax Loss = (Strike Width - Net Credit) x Lot Size',
      desc: 'Combines a Bull Put Spread (below) and Bear Call Spread (above). Profits when the market stays within a range. Highest probability strategy — collects premium from both sides.',
      color: 'border-violet-500/20', badge: 'text-violet-400 bg-violet-500/15',
      highProb: true,
    },
    {
      name: 'Bear Call Spread', type: 'Credit', conviction: 'Mildly Bearish', winRate: '~65-70%',
      legs: 'Sell lower CE + Buy higher CE',
      payoff: 'Max Profit = Net Credit x Lot Size\nMax Loss = (Strike Width - Net Credit) x Lot Size',
      desc: 'Sell an OTM Call and buy a further OTM Call for protection. Profits from time decay when market stays below the sold strike. High probability.',
      color: 'border-red-500/20', badge: 'text-red-400 bg-red-500/15',
      highProb: true,
    },
    {
      name: 'Bear Put Spread', type: 'Debit', conviction: 'Strongly Bearish', winRate: '~55%',
      legs: 'Buy higher PE + Sell lower PE',
      payoff: 'Max Profit = (Strike Width - Net Debit) x Lot Size\nMax Loss = Net Debit x Lot Size',
      desc: 'Buy an ATM Put and sell an OTM Put. Profits when the market drops sharply. Limited risk.',
      color: 'border-orange-500/20', badge: 'text-orange-400 bg-orange-500/15',
    },
    {
      name: 'Long Straddle', type: 'Debit', conviction: 'High Volatility (VIX > 20)', winRate: '~40%',
      legs: 'Buy ATM CE + Buy ATM PE',
      payoff: 'Max Profit = Unlimited\nMax Loss = Total Premium Paid x Lot Size',
      desc: 'Buy both an ATM Call and ATM Put. Profits from a big move in either direction. Used when VIX is elevated and a large swing is expected.',
      color: 'border-yellow-500/20', badge: 'text-yellow-400 bg-yellow-500/15',
    },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">Options Trading</h2>
      <p className="text-xs text-gray-500 mb-6">NIFTY & BANKNIFTY spread strategies with auto market regime detection</p>

      {/* Credit vs Debit explanation */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-dark-700 rounded-xl border border-emerald-500/20 p-5">
          <h3 className="text-sm font-semibold text-emerald-400 mb-2">Credit Spreads (High Probability)</h3>
          <ul className="space-y-1.5 text-xs text-gray-400">
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>You COLLECT premium upfront</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Profit from time decay (theta)</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Win rate: 65-70% — market doesn't need to move in your favor</li>
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Bull Put, Bear Call, Iron Condor</li>
          </ul>
        </div>
        <div className="bg-dark-700 rounded-xl border border-blue-500/20 p-5">
          <h3 className="text-sm font-semibold text-blue-400 mb-2">Debit Spreads (Directional)</h3>
          <ul className="space-y-1.5 text-xs text-gray-400">
            <li className="flex items-start gap-2"><span className="text-blue-400 mt-0.5">&#9679;</span>You PAY premium upfront</li>
            <li className="flex items-start gap-2"><span className="text-blue-400 mt-0.5">&#9679;</span>Need market to move in your direction</li>
            <li className="flex items-start gap-2"><span className="text-blue-400 mt-0.5">&#9679;</span>Win rate: ~55% — higher reward when right</li>
            <li className="flex items-start gap-2"><span className="text-blue-400 mt-0.5">&#9679;</span>Bull Call, Bear Put, Long Straddle</li>
          </ul>
        </div>
      </div>

      {/* Market Regime Detection */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5 mb-6">
        <h3 className="text-sm font-semibold text-white mb-3">Auto Strategy Selection via Market Regime</h3>
        <p className="text-xs text-gray-400 mb-3">The system auto-detects market conditions using India VIX, Put-Call Ratio, and Nifty trend, then selects the highest-probability strategy.</p>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-500">
                {['Regime', 'Conditions', 'Strategy', 'Type', 'Win Rate'].map(h => (
                  <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-xs">
              {[
                ['Strongly Bullish', 'PCR > 1.2, Price > EMAs', 'Bull Call Spread', 'Debit', '~55%'],
                ['Mildly Bullish', 'PCR 0.8-1.2, Above 20 EMA', 'Bull Put Spread', 'Credit', '~65-70%'],
                ['Neutral', 'PCR 0.8-1.2, Near EMAs', 'Iron Condor', 'Credit', '~65-70%'],
                ['Mildly Bearish', 'PCR < 0.8, Below 20 EMA', 'Bear Call Spread', 'Credit', '~65-70%'],
                ['Strongly Bearish', 'PCR < 0.5, Below all MAs', 'Bear Put Spread', 'Debit', '~55%'],
                ['High Volatility', 'VIX > 20', 'Long Straddle', 'Debit', '~40%'],
              ].map((row, i) => (
                <tr key={i} className="border-b border-dark-600/30">
                  <td className="px-3 py-2 text-white font-medium">{row[0]}</td>
                  <td className="px-3 py-2 text-gray-400">{row[1]}</td>
                  <td className="px-3 py-2 text-gray-300">{row[2]}</td>
                  <td className="px-3 py-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${row[3] === 'Credit' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-blue-500/15 text-blue-400'}`}>{row[3]}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-300">{row[4]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6 Strategies */}
      <h3 className="text-sm font-semibold text-white mb-3">6 Spread Strategies</h3>
      <div className="space-y-4 mb-6">
        {spreads.map((s, i) => (
          <div key={i} className={`bg-dark-700 rounded-xl border ${s.color} p-5`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-white">{s.name}</span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${s.badge}`}>{s.type}</span>
              {s.highProb && <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400">HIGH PROB</span>}
              <div className="flex-1" />
              <span className="text-[10px] text-gray-500">{s.conviction}</span>
              <span className="text-[10px] font-mono text-gray-400 ml-2">{s.winRate}</span>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed mb-2">{s.desc}</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-dark-600/50 rounded-lg p-2.5">
                <p className="text-[9px] text-gray-500 uppercase mb-1">Legs</p>
                <p className="text-[11px] text-gray-300 font-medium">{s.legs}</p>
              </div>
              <div className="bg-dark-600/50 rounded-lg p-2.5">
                <p className="text-[9px] text-gray-500 uppercase mb-1">Payoff</p>
                {s.payoff.split('\n').map((line, j) => (
                  <p key={j} className="text-[10px] text-gray-400">{line}</p>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Risk Management */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
        <h3 className="text-sm font-semibold text-white mb-3">Risk Management</h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs text-gray-400">
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Max risk per trade capped at 10% of capital</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Credit spreads: exit at 50% of max profit (lock gains early)</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Stop loss: 1.5x premium for credit, 50% loss for debit</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Intraday: square off by 3:00 PM. Swing: exit 2 days before expiry</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Max 3 positions per underlying (intraday), 2 for swing</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Lot sizes: NIFTY = 25, BANKNIFTY = 15 (updated Nov 2024)</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Orders start at 10:00 AM (let premiums settle), cutoff 2:00 PM</span></div>
          <div className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span><span>Position monitoring every 60 seconds via LTP check</span></div>
        </div>
      </div>
    </>
  )
}

/* ─── Tab: Futures Trading ─── */
function FuturesTab() {
  const strategies = [
    {
      name: 'Volume Breakout', category: 'Momentum',
      indicators: '20-period High/Low, Volume SMA(20), ATR(14)',
      long: 'Completed candle breaks 20-period high + Volume > 2x avg + Breakout > 0.5 ATR + OI: Long Buildup / Short Covering',
      short: 'Completed candle breaks 20-period low + Volume > 2x avg + Breakdown > 0.5 ATR + OI: Short Buildup / Long Unwinding',
      sl: 'ATR-based (1.5x ATR)', rr: '1:2',
      best: 'Strong trending days with high institutional activity',
      color: 'border-amber-500/20', badge: 'text-amber-400 bg-amber-500/15',
    },
    {
      name: 'Candlestick Reversal', category: 'Reversal',
      indicators: '5-bar trend (3-of-5), Hammer/Shooting Star, Engulfing, Volume SMA(20)',
      long: '3-of-5 bars have lower closes (downtrend) + Hammer/Bullish Engulfing + Volume > 1.2x avg + OI: Short Covering / Long Buildup',
      short: '3-of-5 bars have higher closes (uptrend) + Shooting Star/Bearish Engulfing + Volume > 1.2x avg + OI: Long Unwinding / Short Buildup',
      sl: 'Reversal candle low/high + ATR buffer', rr: '1:1.5',
      best: 'V-shaped reversals at support/resistance levels',
      color: 'border-rose-500/20', badge: 'text-rose-400 bg-rose-500/15',
    },
    {
      name: 'Mean Reversion', category: 'Value',
      indicators: 'Bollinger Bands (20, 2), RSI(14), 200 EMA',
      long: 'Price within bottom 15% of BB width + RSI < 35 + Price > 200 EMA + OI: Short Covering / Long Buildup',
      short: 'Price within top 15% of BB width + RSI > 65 + Price < 200 EMA + OI: Long Unwinding / Short Buildup',
      sl: 'Beyond BB band or ATR-based (tighter wins)', rr: 'Variable (target = middle BB)',
      best: 'Range-bound, mean-reverting markets with low VIX',
      color: 'border-cyan-500/20', badge: 'text-cyan-400 bg-cyan-500/15',
    },
    {
      name: 'EMA & RSI Pullback', category: 'Trend Continuation',
      indicators: '50 EMA, RSI(14), Volume SMA(20)',
      long: 'Close > 50 EMA + within 3% of EMA (pullback) + RSI 40-55 + Volume > 1.5x avg + OI: Long Buildup / Short Covering',
      short: 'Close < 50 EMA + within 3% of EMA + RSI 45-60 + Volume > 1.5x avg + OI: Short Buildup / Long Unwinding',
      sl: 'ATR-based (1.5x ATR)', rr: '1:2',
      best: 'Clear trending markets with healthy pullbacks',
      color: 'border-violet-500/20', badge: 'text-violet-400 bg-violet-500/15',
    },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">Futures Trading</h2>
      <p className="text-xs text-gray-500 mb-6">NSE F&O stock futures with OI sentiment analysis, auto regime detection, and margin-based lot sizing</p>

      {/* 3-Layer Architecture */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5 mb-6">
        <h3 className="text-sm font-semibold text-white mb-3">3-Layer Architecture</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-dark-600/50 rounded-lg p-4 border border-amber-500/10">
            <div className="text-[10px] font-bold text-amber-400 uppercase mb-2">Layer 1: OI Sentiment</div>
            <p className="text-xs text-gray-400 leading-relaxed">Batch-fetches OI data for ~180 F&O stocks via Fyers. Classifies each into: Long Buildup (price up + OI up), Short Covering (price up + OI down), Short Buildup (price down + OI up), Long Unwinding (price down + OI down).</p>
          </div>
          <div className="bg-dark-600/50 rounded-lg p-4 border border-blue-500/10">
            <div className="text-[10px] font-bold text-blue-400 uppercase mb-2">Layer 2: Strategy Screeners</div>
            <p className="text-xs text-gray-400 leading-relaxed">4 technical strategies scan all F&O stocks. Each strategy fires ONLY when OI sentiment aligns (e.g., Volume Breakout BUY requires Long Buildup or Short Covering). Uses completed candles to avoid lookahead bias.</p>
          </div>
          <div className="bg-dark-600/50 rounded-lg p-4 border border-green-500/10">
            <div className="text-[10px] font-bold text-green-400 uppercase mb-2">Layer 3: Margin Sizing</div>
            <p className="text-xs text-gray-400 leading-relaxed">Position size = min(margin lots, risk lots). Intraday margin: ~10%. Risk cap: 5% per trade. Lot-based sizing ensures quantity is always a valid multiple. Brokerage-aware: skips trades where charges eat {'>'}50% of reward.</p>
          </div>
        </div>
      </div>

      {/* Auto Regime Detection */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5 mb-6">
        <h3 className="text-sm font-semibold text-white mb-3">Auto Strategy Selection via Market Regime</h3>
        <p className="text-xs text-gray-400 mb-3">The system analyzes NIFTY trend (20 EMA + 50 SMA + ADX strength), India VIX (volatility), and aggregate OI sentiment across F&O stocks to auto-select which strategies activate.</p>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-500">
                {['Market Condition', 'VIX', 'Auto-Selected Strategies', 'Logic'].map(h => (
                  <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-xs">
              {[
                ['Strong Trend (Bull/Bear)', 'High (>20)', 'Volume Breakout', 'Momentum thrives in volatile trends'],
                ['Strong Trend', 'Normal', 'Volume Breakout + EMA Pullback', 'Trend continuation + breakout'],
                ['Strong Trend', 'Low (<13)', 'EMA Pullback', 'Calm trend = pullback entries'],
                ['Pullback in Trend', 'Any', 'EMA Pullback + Candlestick Reversal', 'Catch the bounce'],
                ['Sideways / Range', 'Normal', 'Mean Reversion + Candlestick Reversal', 'Fade the extremes'],
                ['Sideways', 'Low', 'Mean Reversion', 'Range-bound + low vol = mean reversion'],
                ['Sideways', 'High', 'Volume Breakout + Candlestick Reversal', 'Breakout from range with vol'],
              ].map((row, i) => (
                <tr key={i} className="border-b border-dark-600/30">
                  <td className="px-3 py-2 text-white font-medium">{row[0]}</td>
                  <td className="px-3 py-2 text-gray-400">{row[1]}</td>
                  <td className="px-3 py-2 text-amber-400 font-medium">{row[2]}</td>
                  <td className="px-3 py-2 text-gray-500 text-[11px]">{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4 Strategies */}
      <h3 className="text-sm font-semibold text-white mb-3">4 Futures Strategies</h3>
      <div className="space-y-4 mb-6">
        {strategies.map((s, i) => (
          <div key={i} className={`bg-dark-700 rounded-xl border ${s.color} p-5`}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-semibold text-white">{s.name}</span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${s.badge}`}>{s.category}</span>
              <div className="flex-1" />
              <span className="text-[10px] font-mono text-gray-400">R:R {s.rr}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 mb-3">
              <div>
                <p className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider mb-0.5">Indicators</p>
                <p className="text-xs text-gray-300">{s.indicators}</p>
              </div>
              <div>
                <p className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider mb-0.5">Stop-Loss</p>
                <p className="text-xs text-gray-400">{s.sl}</p>
              </div>
              <div>
                <p className="text-[9px] font-semibold text-green-400/70 uppercase tracking-wider mb-0.5">Long Setup</p>
                <p className="text-xs text-gray-400 leading-relaxed">{s.long}</p>
              </div>
              <div>
                <p className="text-[9px] font-semibold text-red-400/70 uppercase tracking-wider mb-0.5">Short Setup</p>
                <p className="text-xs text-gray-400 leading-relaxed">{s.short}</p>
              </div>
            </div>
            <div className="bg-dark-600/50 rounded-lg p-2.5">
              <p className="text-[9px] text-gray-500 uppercase mb-0.5">Best Market Conditions</p>
              <p className="text-[11px] text-gray-300">{s.best}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 4 Engines */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5 mb-6">
        <h3 className="text-sm font-semibold text-white mb-3">4 Trading Engines</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-500">
                {['Engine', 'Mode', 'Product', 'Max Positions', 'Exit'].map(h => (
                  <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-xs">
              {[
                ['Intraday Live', 'Live orders via Fyers', 'INTRADAY', '4', 'Square-off 3:15 PM'],
                ['Intraday Paper', 'Virtual (no real orders)', 'Virtual', '8', 'Square-off 3:15 PM'],
                ['Swing Live', 'Live MARGIN orders', 'MARGIN', '2', 'Rollover or close 2d before expiry'],
                ['Swing Paper', 'Virtual swing', 'Virtual', '5', 'Close 2d before expiry'],
              ].map((row, i) => (
                <tr key={i} className="border-b border-dark-600/30">
                  <td className="px-3 py-2 text-white font-medium">{row[0]}</td>
                  <td className="px-3 py-2 text-gray-400">{row[1]}</td>
                  <td className="px-3 py-2"><span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400">{row[2]}</span></td>
                  <td className="px-3 py-2 text-gray-300">{row[3]}</td>
                  <td className="px-3 py-2 text-gray-400">{row[4]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Risk Management */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5 mb-6">
        <h3 className="text-sm font-semibold text-white mb-3">Risk Management</h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs text-gray-400">
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Exchange-level SL-M order on every position (not just polling)</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>5% risk per trade (configurable). Strict lot-size enforcement</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Daily loss limit: 5% of capital — engine stops opening new positions</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Per-position max loss: 3% of capital — force close if breached</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Liquidity filter: skips contracts with OI {'<'} 5,000 or volume {'<'} 50,000</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Brokerage-aware: skips trades where charges {'>'} 50% of expected reward</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Intraday margin: ~10% (MIS). Swing margin: ~20% (MARGIN)</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Holiday-aware expiry: shifts to Wednesday if Thursday is NSE holiday</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Square-off retry: 3 attempts with backoff on API failure</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Swing SL-M orders re-placed daily (DAY validity expires overnight)</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Contract rollover: close current month + re-enter next month near expiry</span></div>
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>Spot-to-futures basis adjustment: SL/target adjusted for futures premium</span></div>
        </div>
      </div>

      {/* Position Sizing */}
      <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
        <h3 className="text-sm font-semibold text-white mb-3">Position Sizing (Margin-Based)</h3>
        <div className="bg-dark-600/50 rounded-lg p-4 font-mono text-xs text-gray-300 leading-relaxed">
          <p>margin_per_lot = lot_size x price x 10% (intraday) or 20% (swing)</p>
          <p>max_lots_by_margin = capital / margin_per_lot</p>
          <p>max_lots_by_risk = (capital x 5%) / (SL_distance x lot_size)</p>
          <p className="text-amber-400 mt-2">num_lots = min(margin, risk)  // most conservative wins</p>
        </div>
        <div className="mt-3 text-xs text-gray-500">
          <p>Recommended minimum capital: <span className="text-white font-medium">Rs 1,00,000</span> (5+ stocks tradeable)</p>
          <p>Optimal capital: <span className="text-white font-medium">Rs 2,00,000+</span> (24+ stocks, good screener coverage)</p>
        </div>
      </div>
    </>
  )
}

/* ─── Tab: App Pages ─── */
function AppPagesTab() {
  const pages = [
    { name: 'Dashboard', desc: 'Home screen showing all 4 engines (Intraday Live, Intraday Paper, Swing Live, Swing Paper) with live status. Overall P&L, win rate, open positions, strategy performance split by Intraday and Swing, stock-wise P&L bars, and order summary.', color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' },
    { name: 'Intraday Trading', desc: 'Auto regime mode: system detects NIFTY trend + VIX + ADX and picks from all 6 strategies automatically. Max 2 orders per scan (staggered). VIX > 18: skips 5m, uses 15m only. SL min 1.2%. Daily 5% loss limit. Order fill verification on Fyers. Fyers P&L shown as source of truth for live mode.', color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
    { name: 'Swing Trading', desc: 'Live/Paper toggle. BUY-only (CNC delivery, no short selling). Morning scan at 9:20 AM, retries every 30 min if slot open. Max 1 position (live) / 5 (paper). Price filter: Rs 100 - Rs 1,500. Daily Strategy Performance shows per-day breakdown.', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
    { name: 'Backtest', desc: 'Test any strategy on a specific past date to see what trades would have triggered, their entry/exit prices, and overall performance. Great for validating strategies before deploying.', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
    { name: 'Positions & Orders', desc: 'Real-time view of your open positions and complete order book from Fyers. Filter orders by status — Filled, Pending, Rejected, or Cancelled.', color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500/20' },
    { name: 'Trade Log', desc: 'Complete history of all trades (auto, paper, swing, swing paper) with strategy tags, entry/exit prices, P&L, broker charges, and net profit. Filter by source, strategy, or date range. Totals row shows filtered P&L, charges, net P&L, and win rate.', color: 'text-pink-400', bg: 'bg-pink-500/10 border-pink-500/20' },
    { name: 'Daily P&L', desc: "Day-wise profit/loss with Live/Paper toggle. Pie charts show profit vs loss breakdown and strategy-wise performance. Today's data from Fyers (source of truth), historical from trade logger.", color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20' },
    { name: 'Algo Specialists', desc: '6 AI analysis agents (Strategist, Engineer, Data Scientist, Risk Manager, QA Expert, Performance Analyst). Single "Generate" button runs all at once. Shows findings, deployable recommendations, and manual insights.', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
    { name: 'Options Intraday (Live/Paper)', desc: 'NIFTY/BANKNIFTY spread trading. Auto regime every 15 min (VIX + PCR + daily trend + intraday direction). 6 strategies auto-selected. Intraday direction prevents wrong-side spreads. Scan every 15 min. 30 min loss cooldown after losing trade. Daily 5% loss limit. Orders 10 AM - 2 PM, square-off 3 PM.', color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/20' },
    { name: 'Options Swing (Live/Paper)', desc: 'Monthly expiry options spreads that carry over days. Same 6 strategies with auto regime detection. Exit on profit target, stop loss, or 2 days before expiry. Max 2 positions. Scans every 4 hours during market hours.', color: 'text-teal-400', bg: 'bg-teal-500/10 border-teal-500/20' },
    { name: 'Futures Intraday (Live/Paper)', desc: 'NSE F&O stock futures with 3-layer system: OI sentiment analysis + 4 strategy screeners + margin-based lot sizing. Auto regime detection selects strategies based on NIFTY trend, VIX, and aggregate OI. Exchange-level SL-M on every position. Daily 5% loss limit. Orders 12 PM - 2 PM, square-off 3:15 PM. Max 4 positions (live) / 8 (paper).', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
    { name: 'Futures Swing (Live/Paper)', desc: 'MARGIN product futures that carry over days. Same 4 strategies with OI filter. Exchange SL-M re-placed daily (DAY validity). Contract rollover near expiry: close current month, re-enter next month. Max 2 positions (live) / 5 (paper). Scans every 4 hours. Per-position 3% max loss cap.', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">App Pages</h2>
      <p className="text-xs text-gray-500 mb-6">What you'll find in each section of the app</p>

      <div className="space-y-3">
        {pages.map((p, i) => (
          <div key={i} className={`flex items-start gap-4 rounded-xl border p-4 ${p.bg}`}>
            <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${p.color.replace('text-', 'bg-')}`} />
            <div>
              <h3 className={`text-sm font-semibold ${p.color} mb-1`}>{p.name}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">{p.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

/* ─── Tab: Rules & Notes ─── */
function RulesTab() {
  const rules = [
    { label: 'Market Hours', value: '9:15 AM - 3:30 PM IST (Mon-Fri)', icon: Clock },
    { label: 'Stock Universe', value: 'Nifty 500 stocks', icon: BarChart3 },
    { label: 'Equity Risk/Trade', value: '2% of capital (SL min 1.2%)', icon: Shield },
    { label: 'Intraday Positions', value: '4 (live) / 10 (paper)', icon: Target },
    { label: 'Swing Positions', value: '1 (live) / 5 (paper)', icon: Repeat },
    { label: 'Intraday Scan', value: 'On-demand — re-scans when slot opens', icon: Search },
    { label: 'Intraday Orders', value: '12:00 PM - 2:00 PM', icon: Clock },
    { label: 'Auto Square-Off', value: '3:15 PM (intraday only)', icon: Square },
    { label: 'Swing Scan', value: '9:20 AM + retry every 30 min', icon: Search },
    { label: 'Swing Direction', value: 'BUY only (no CNC short selling)', icon: TrendingUp },
    { label: 'Swing Nifty Filter', value: 'Blocks BUY only when Nifty < 50 SMA', icon: Shield },
    { label: 'Intraday Price Range', value: 'Rs 50 - Rs 5,000', icon: IndianRupee },
    { label: 'Swing Price Range', value: 'Rs 100 - Rs 1,500', icon: IndianRupee },
    { label: 'Intraday Product', value: 'INTRADAY (MIS)', icon: Zap },
    { label: 'Swing Product', value: 'CNC (delivery, carries overnight)', icon: Repeat },
    { label: 'Futures Universe', value: '~180 NSE F&O stocks with lot sizes', icon: BarChart3 },
    { label: 'Futures Risk/Trade', value: '5% of capital (margin-based lots)', icon: Shield },
    { label: 'Futures Daily Loss', value: '5% of capital — engine stops', icon: AlertTriangle },
    { label: 'Futures Intraday Margin', value: '~10% of contract value', icon: IndianRupee },
    { label: 'Futures Swing Margin', value: '~20% of contract value', icon: IndianRupee },
    { label: 'Futures OI Filter', value: 'Strategies fire only when OI sentiment aligns', icon: Eye },
  ]

  const notes = [
    'Trading involves risk. Never trade money you cannot afford to lose. Always paper trade first.',
    'You need a Fyers broker account with API access. Get credentials from myapi.fyers.in.',
    'Start the app and login to Fyers before 9:15 AM so you are ready when the market opens.',
    'Fyers token expires daily — you need to re-login each morning.',
    'Intraday engine stops after square-off at 3:15 PM — needs restart next day. Swing trader runs continuously.',
    'Brokerage is flat Rs 20/order regardless of stock price. Charges include STT + exchange fees + GST + stamp duty.',
    'Swing trades use CNC (delivery) — positions carry over days. SL & target orders are re-placed each morning since CNC orders expire daily.',
    'Intraday price filter (Rs 50 - Rs 5,000) prevents tiny qty trades on expensive stocks like MARUTI. Swing filter (Rs 100 - Rs 1,500) keeps position sizing meaningful.',
    'Each trading page shows Daily Strategy Performance — which strategy worked each day, with timeframe, W/L, and per-trade breakdown.',
    'Futures trading requires minimum Rs 1,00,000 capital for meaningful stock coverage (5+ stocks). Rs 2,00,000+ recommended for 24+ stocks.',
    'Futures use OI sentiment filtering — strategies only fire when Open Interest data confirms the direction (Long Buildup, Short Covering, etc.).',
    'Futures swing positions have exchange-level SL-M orders that are re-placed each morning (DAY validity). Contract rollover happens automatically near expiry.',
    'Auto regime mode analyzes NIFTY trend + VIX + aggregate OI to pick the best strategy — no manual selection needed.',
  ]

  return (
    <>
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-5">Key Rules</h2>
        <div className="grid grid-cols-2 gap-x-8 gap-y-3">
          {rules.map((r, i) => (
            <div key={i} className="flex items-center gap-3 py-1">
              <r.icon size={14} className="text-gray-500 flex-shrink-0" />
              <span className="text-xs text-gray-400">{r.label}:</span>
              <span className="text-xs text-white font-medium">{r.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-yellow-500/5 rounded-2xl border border-yellow-500/20 p-6">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle size={16} className="text-yellow-400" />
          <h2 className="text-sm font-semibold text-yellow-400">Good to Know</h2>
        </div>
        <ul className="space-y-2.5">
          {notes.map((note, i) => (
            <li key={i} className="flex items-start gap-2">
              <CheckCircle2 size={12} className="text-yellow-500/60 mt-0.5 flex-shrink-0" />
              <span className="text-xs text-gray-400 leading-relaxed">{note}</span>
            </li>
          ))}
        </ul>
      </div>
    </>
  )
}

/* ─── Main Component ─── */
export default function AboutPage() {
  const [activeTab, setActiveTab] = useState('overview')

  const renderTab = () => {
    switch (activeTab) {
      case 'overview': return <OverviewTab />
      case 'how-it-works': return <HowItWorksTab />
      case 'get-started': return <GetStartedTab />
      case 'trading-day': return <TradingDayTab />
      case 'strategies': return <StrategiesTab />
      case 'options': return <OptionsTab />
      case 'futures': return <FuturesTab />
      case 'pages': return <AppPagesTab />
      case 'rules': return <RulesTab />
      default: return <OverviewTab />
    }
  }

  return (
    <div className="max-w-4xl">
      {/* Tab Bar */}
      <div className="flex gap-1 mb-6 bg-dark-700 rounded-xl border border-dark-500 p-1.5 overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                isActive
                  ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                  : 'text-gray-400 hover:text-white hover:bg-dark-600 border border-transparent'
              }`}
            >
              <Icon size={13} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      {renderTab()}
    </div>
  )
}
