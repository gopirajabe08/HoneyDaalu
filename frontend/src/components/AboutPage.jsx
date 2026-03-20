import React, { useState, useEffect } from 'react'
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
  { id: 'auto-system', label: 'Auto System', icon: Repeat },
  { id: 'strategies', label: 'Equity', icon: Target },
  { id: 'options', label: 'Options', icon: BarChart3 },
  { id: 'futures', label: 'Futures', icon: TrendingUp },
  { id: 'pages', label: 'App Pages', icon: BookOpen },
  { id: 'shortcuts', label: 'Shortcuts', icon: Zap },
  { id: 'e2e-flow', label: 'E2E Flow', icon: Layers },
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
              It scans <span className="text-white font-medium">Nifty 500 stocks</span> using 9 proven technical strategies,
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
          <p className="text-xs text-gray-400 leading-relaxed">Scans all Nifty 500 stocks using 9 technical strategies to find buy/sell signals with clear entry, stop-loss, and target.</p>
        </div>
        <div className="bg-dark-700 rounded-xl border border-dark-500 p-5">
          <ShoppingCart size={20} className="text-green-400 mb-3" />
          <h3 className="text-sm font-semibold text-white mb-1">Trade</h3>
          <p className="text-xs text-gray-400 leading-relaxed">Automatically places orders on Fyers with built-in SL & target. Risks only 2% of your capital per trade. Trailing SL locks in profits after 1% gain. Multi-day drawdown breaker (15% over 5 days) reduces exposure. No manual intervention needed.</p>
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
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Auto regime mode with dynamic re-detection every scan cycle</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>On-demand scan: initial scan at 10:30 AM, re-scans when a slot opens</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Play4 Supertrend prioritized. Volume confirmation on all signals</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Conviction-based signal ranking. VIX elevated zone (16-20) reduces positions</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Places entry + SL orders on Fyers, monitors target every 20s</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Max 6 positions (live) / 10 positions (paper)</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Orders: 10:30 AM - 2:00 PM. Square-off at 3:15 PM</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>Uses 5m / 15m candle timeframes</li>
            <li className="flex items-start gap-2"><span className="text-orange-400 mt-0.5">&#9679;</span>All 9 strategies available. Price filter: Rs 50 - Rs 5,000</li>
          </ul>
        </div>
        <div className="bg-dark-700 rounded-xl p-5 border border-emerald-500/20">
          <h3 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
            <Repeat size={14} /> Swing Mode
          </h3>
          <ul className="space-y-2 text-xs text-gray-400">
            <li className="flex items-start gap-2"><span className="text-emerald-400 mt-0.5">&#9679;</span>Morning scan at 9:20 AM. Retries every 2 hours until 2 PM if slot open</li>
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
      desc: 'Once confident with paper results, switch to Live mode using the toggle on the Intraday or Swing page. The system will scan at 10:30 AM (intraday) or 9:20 AM (swing), place real orders, manage SL/target, and square off — all automatically.',
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
    { time: '9:15 AM', title: 'Market Opens', desc: 'Start intraday engine (Live or Paper). Swing engine scans at 9:20 AM for overnight signals. Intraday waits until 10:30 AM before placing orders.', color: 'bg-green-500', textColor: 'text-green-400', highlight: true },
    { time: '9:20 AM', title: 'Swing Morning Scan', desc: "Swing trader scans all 4 strategies on daily candles. If no signal found and slot open, retries every 2 hours until 2 PM. BUY signals only.", color: 'bg-emerald-500', textColor: 'text-emerald-400' },
    { time: '10:30 AM', title: 'Equity Intraday Orders Begin', desc: 'Initial full scan runs to fill all position slots. Auto regime with dynamic re-detection. Play4 Supertrend prioritized. Volume confirmation + conviction-based ranking.', color: 'bg-orange-500', textColor: 'text-orange-400', highlight: true },
    { time: '10:30 AM - 2:00 PM', title: 'Active Trading', desc: 'Monitors positions every 20s. When a trade closes (SL/target), scans again to fill the slot. Max 6 live / 10 paper positions. VIX elevated zone (16-20) reduces positions.', color: 'bg-orange-500', textColor: 'text-orange-400' },
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
    {
      num: '#7', name: 'Opening Range Breakout (ORB)', type: 'Momentum',
      indicators: 'Opening Range (9:15-9:45 AM), Volume SMA20',
      how: 'Price breaks above/below 30-min high/low with volume > 1.3x and strong body (>50% of range). Captures morning momentum on trending and gap days.',
      exit: '1:2 risk-reward target.',
      sl: 'Opposite side of opening range (min 1.2% ATR floor).',
      rr: '1:2',
      intraday: { timeframes: ['15m'], best: '15m', note: '15m captures the breakout cleanly. Best on trending days and gap days — strong directional moves after the opening range sets.' },
      swing: null,
      color: 'border-amber-500/20', badge: 'text-amber-400 bg-amber-500/15',
    },
    {
      num: '#8', name: 'RSI Divergence Reversal', type: 'Reversal',
      indicators: 'RSI (14), Swing High/Low detection',
      how: 'Price makes new high but RSI makes lower high = bearish divergence. Price makes new low but RSI makes higher low = bullish divergence. Detects trend exhaustion before price reverses.',
      exit: '1:2 risk-reward target.',
      sl: 'Beyond last swing extreme (min 1.2% ATR floor).',
      rr: '1:2',
      intraday: { timeframes: ['15m'], best: '15m', note: '15m gives clean divergence signals. Best for catching reversals, pullbacks, oversold bounces, and trend exhaustion points.' },
      swing: { timeframes: ['1h', '1d'], best: '1d', note: 'Daily RSI divergence catches multi-day reversals and oversold bounces. Higher timeframes = stronger divergence signals.' },
      color: 'border-rose-500/20', badge: 'text-rose-400 bg-rose-500/15',
    },
    {
      num: '#9', name: 'Gap Analysis (Gap & Go / Gap Fill)', type: 'Momentum / Reversal',
      indicators: 'Previous Close, Opening Range, Volume SMA20',
      how: 'Gap > 1% from previous close. Two modes: Gap & Go (continuation if price holds above gap) or Gap Fill (reversal if price starts filling the gap). Volume > 1.3x confirms.',
      exit: '1:2 R:R (Gap & Go) or previous close (Gap Fill).',
      sl: 'Opposite side of gap range.',
      rr: '1:2',
      intraday: { timeframes: ['15m'], best: '15m', note: '15m captures gap reactions after first 30 min. Best on morning gaps from overnight news, earnings, or event days.' },
      swing: null,
      color: 'border-teal-500/20', badge: 'text-teal-400 bg-teal-500/15',
    },
  ]

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">9 Trading Strategies</h2>
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
            <p className="text-xs text-gray-400 leading-relaxed">8 strategies scan all F&O stocks (4 futures-specific + Supertrend, ORB, RSI Divergence, Gap Analysis from equity). Each strategy fires ONLY when OI sentiment aligns (e.g., Volume Breakout BUY requires Long Buildup or Short Covering). Uses completed candles to avoid lookahead bias.</p>
          </div>
          <div className="bg-dark-600/50 rounded-lg p-4 border border-green-500/10">
            <div className="text-[10px] font-bold text-green-400 uppercase mb-2">Layer 3: Margin Sizing</div>
            <p className="text-xs text-gray-400 leading-relaxed">Position size = min(margin lots, risk lots). Intraday margin: ~10%. Risk cap: 2% per trade. Lot-based sizing ensures quantity is always a valid multiple. Brokerage-aware: skips trades where charges eat {'>'}50% of reward.</p>
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
      <h3 className="text-sm font-semibold text-white mb-3">8 Futures Strategies (4 futures-specific + Supertrend, ORB, RSI Divergence, Gap Analysis)</h3>
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
          <div className="flex items-start gap-2"><span className="text-amber-400 mt-0.5">&#9679;</span><span>2% risk per trade (configurable). Strict lot-size enforcement</span></div>
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
    { name: 'Intraday Trading', desc: 'Auto regime mode with dynamic re-detection. Play4 Supertrend prioritized. Volume confirmation on all signals. Conviction-based signal ranking. VIX elevated zone (16-20) reduces positions. Orders 10:30 AM - 2 PM. Max 2 orders per scan (staggered). SL min 1.2%. Daily 5% loss limit. Order fill verification on Fyers. Fyers P&L shown as source of truth for live mode.', color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
    { name: 'Swing Trading', desc: 'Live/Paper toggle. BUY-only (CNC delivery, no short selling). Morning scan at 9:20 AM, retries every 2 hours if slot open. Max 1 position (live) / 5 (paper). Price filter: Rs 100 - Rs 1,500. Daily Strategy Performance shows per-day breakdown.', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
    { name: 'Backtest', desc: 'Test any strategy on a specific past date to see what trades would have triggered, their entry/exit prices, and overall performance. Great for validating strategies before deploying.', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
    { name: 'Positions & Orders', desc: 'Real-time view of your open positions and complete order book from Fyers. Filter orders by status — Filled, Pending, Rejected, or Cancelled.', color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500/20' },
    { name: 'Trade Log', desc: 'Complete history of all trades (auto, paper, swing, swing paper) with strategy tags, entry/exit prices, P&L, broker charges, and net profit. Filter by source, strategy, or date range. Totals row shows filtered P&L, charges, net P&L, and win rate.', color: 'text-pink-400', bg: 'bg-pink-500/10 border-pink-500/20' },
    { name: 'Daily P&L', desc: "Day-wise profit/loss with Live/Paper toggle. Pie charts show profit vs loss breakdown and strategy-wise performance. Today's data from Fyers (source of truth), historical from trade logger.", color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20' },
    { name: 'Algo Specialists', desc: '6 AI analysis agents (Strategist, Engineer, Data Scientist, Risk Manager, QA Expert, Performance Analyst). Single "Generate" button runs all at once. Shows findings, deployable recommendations, and manual insights.', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
    { name: 'Options Intraday (Live/Paper)', desc: 'NIFTY/BANKNIFTY spread trading. Auto regime every 15 min (VIX + PCR + daily trend + intraday direction). 6 strategies auto-selected. Intraday direction prevents wrong-side spreads. Scan every 15 min. 30 min loss cooldown after losing trade. Daily 5% loss limit. Orders 10 AM - 2 PM, square-off 3 PM.', color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/20' },
    { name: 'Options Swing (Live/Paper)', desc: 'Monthly expiry options spreads that carry over days. Same 6 strategies with auto regime detection. Exit on profit target, stop loss, or 2 days before expiry. Max 2 positions. Scans every 4 hours during market hours.', color: 'text-teal-400', bg: 'bg-teal-500/10 border-teal-500/20' },
    { name: 'Futures Intraday (Live/Paper)', desc: 'NSE F&O stock futures with 3-layer system: OI sentiment hard filter + 8 strategy screeners (4 futures-specific + Supertrend, ORB, RSI Divergence, Gap Analysis) + margin-based lot sizing. Auto regime detection selects strategies based on NIFTY trend, VIX, and aggregate OI. Exchange-level SL-M on every position. 2% risk/trade. Daily 5% loss limit. Orders 11 AM - 2 PM, square-off 3:15 PM. Max 4 positions (live) / 8 (paper).', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
    { name: 'Futures Swing (Live/Paper)', desc: 'MARGIN product futures that carry over days. Same 8 strategies (4 futures-specific + Supertrend, ORB, RSI Divergence, Gap Analysis) with OI filter. Exchange SL-M re-placed daily (DAY validity). Contract rollover near expiry: close current month, re-enter next month. Max 2 positions (live) / 5 (paper). Scans every 4 hours. Per-position 3% max loss cap.', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
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

/* ─── Tab: Autonomous Trading System ─── */
function AutoSystemTab() {
  const timelineSteps = [
    { time: '9:15 AM', title: 'YOU — Press Start', desc: 'Open browser → localhost:3000. Start all 6 engines (Equity Intraday, Equity Swing, Options Intraday, Options Swing, Futures Intraday, Futures Swing). Close browser. Done for the day. 9 equity strategies + 8 futures strategies + 6 options strategies auto-selected by regime.', role: 'manual', icon: '👆' },
    { time: '9:20 AM', title: 'Swing Morning Scan', desc: 'Equity + Futures swing engines scan all strategies on daily candles. BUY-only for equity (CNC). If no signal, retry in 2 hours.', role: 'auto', icon: '🔍' },
    { time: '9:50 AM', title: 'Options Regime Detection', desc: 'Analyzes NIFTY/BANKNIFTY trend, VIX, PCR. Picks from 6 options strategies (spreads, condors, straddles). Iron condor blocked when VIX > 16.', role: 'auto', icon: '📊' },
    { time: '10:00 AM', title: 'Options Orders Begin', desc: 'Scans for option spread opportunities. Places virtual orders with slippage simulation + brokerage estimation. Max 3 positions per underlying.', role: 'auto', icon: '📈' },
    { time: '10:30 AM', title: 'Equity Intraday Begins', desc: 'Regime detected: NIFTY trend + VIX + ADX + intraday direction → picks from 9 strategies. Play4 Supertrend prioritized (best performer). Play7 ORB for morning breakouts, Play8 RSI Divergence for reversals, Play9 Gap for gap days. Volume confirmation filters noise. Conviction score ranks signals. Max 2 orders per scan.', role: 'auto', icon: '🚀' },
    { time: '11:00 AM', title: 'Futures Intraday Begins', desc: 'Futures regime + OI sentiment analysis. OI hard filter blocks counter-sentiment trades. 2% risk per trade. Margin-based lot sizing.', role: 'auto', icon: '📉' },
    { time: '10:30–2:00', title: 'Active Trading Loop', desc: 'Every 20 seconds: check LTP for all positions → SL hit? Close. Target hit? Close. Trailing SL activates after 1% profit — locks in 50% of max gain. When slot opens → re-detect regime (may have shifted mid-day) → scan → rank by conviction → place best signal.', role: 'auto', icon: '🔄' },
    { time: '2:00 PM', title: 'Order Cutoff', desc: 'No new intraday orders. Existing positions monitored every 20s until square-off. Swing positions continue.', role: 'auto', icon: '🚫' },
    { time: '3:00 PM', title: 'Options Square-off', desc: 'All intraday option spreads closed. Swing option positions carry overnight.', role: 'auto', icon: '⏹️' },
    { time: '3:15 PM', title: 'Equity + Futures Square-off', desc: 'All intraday positions force-closed. Swing positions carry overnight. Trade data logged.', role: 'auto', icon: '⏹️' },
    { time: '3:15 PM', title: 'AUTO — Daily Report Generated', desc: 'Counts all trades by strategy + source. Calculates win rate, expectancy, P&L per strategy. Compares with last 3-5 days. Generates insights + recommendations. Saved to tracking/daily/.', role: 'auto', icon: '📋' },
    { time: '3:15 PM', title: 'AUTO — Quant Strategist (Auto-Tuner)', desc: 'Analyzes rolling 3-5 day performance. Adjusts strategy conviction boosts (best→1.4x, worst→0.5x). SL hit rate > 50% for 2+ days → widens ATR by 0.25. Too few trades → loosens volume filter. Win rate < 35% → tightens volume filter. All within guardrails (can never exceed bounds).', role: 'auto', icon: '🧠' },
    { time: '3:15 PM', title: 'AUTO — QA Testing (34 checks)', desc: 'All strategy modules import? Parameters within bounds? Regime detection works? Volume filters intact? Trailing SL fields valid? If ANY check fails → ALL changes rolled back automatically. System safe for tomorrow.', role: 'auto', icon: '✅' },
    { time: '3:16 PM', title: 'System Ready for Tomorrow', desc: 'Optimized parameters saved. Swing positions monitored overnight. Next morning: press Start → system uses yesterday\'s optimized config.', role: 'auto', icon: '🌙' },
  ]

  const autoTuneParams = [
    { param: 'Strategy Conviction Boosts', what: 'Which strategy gets picked first from scan results', how: 'Ranks by rolling expectancy (₹/trade). Best=1.4x, worst=0.5x. Recalculates daily.', bounds: '0.3x – 2.0x', frequency: 'Daily' },
    { param: 'ATR Stop Loss Multiplier', what: 'How wide the stop loss is (distance from entry)', how: 'SL hit rate > 50% for 2+ days → widen by 0.25. SL rate < 15% → tighten by 0.25.', bounds: '1.5x – 4.0x (max ±0.25/day)', frequency: 'When pattern detected (3+ days)' },
    { param: 'Volume Filter Threshold', what: 'Minimum volume required to accept a signal', how: '< 3 trades/day for 3 days → loosen by 0.1. Win rate < 35% → tighten by 0.1.', bounds: '1.0x – 2.0x (max ±0.1/day)', frequency: 'When pattern detected (3+ days)' },
    { param: 'Direction Bias', what: 'Whether BUY or SELL signals are preferred', how: 'If one direction loses > ₹3K over 3 days while other profits → logged as observation. Regime detection handles dynamically.', bounds: 'Observation only', frequency: 'When detected' },
    { param: 'Trailing Stop Loss', what: 'Locks in profits as trade moves favorably', how: 'Activates after 1% profit. Trails at 50% of max profit. SL only tightens, never loosens.', bounds: 'Min = original SL, Max = current price', frequency: 'Every 20s position check' },
  ]

  const safetyGuardrails = [
    'Every parameter has absolute min/max bounds — can NEVER exceed',
    'Max ONE step change per parameter per day — no dramatic shifts',
    'Needs 3+ days of consistent signal before acting (no single-day reactions)',
    'Every change logged in changelog.json with full data backing',
    '34-point QA test runs AFTER every change',
    'If QA fails → ALL changes auto-rolled back to pre-tune values',
    'Strategy boosts recalculate daily — bad day auto-corrects next day',
    'All changes visible in Tracker sidebar (right panel)',
    'Trailing stop loss: locks in 50% of peak profit after 1% gain threshold',
    'Multi-day drawdown breaker: 15% loss over 5 days → reduces to 1 order/scan',
    'Fyers auto-reconnect: live traders detect disconnect and attempt headless re-login',
  ]

  return (
    <>
      <div className="bg-gradient-to-br from-purple-500/10 via-dark-700 to-blue-500/10 rounded-2xl border border-dark-500 p-6 mb-6">
        <h2 className="text-xl font-bold text-white mb-2">Autonomous Trading System</h2>
        <p className="text-sm text-gray-400">
          Fully automated: you press Start at 9:15 AM, the system trades, optimizes, tests, and prepares for tomorrow.
          No manual intervention needed for strategy selection, risk management, or parameter tuning.
        </p>
      </div>

      {/* Daily Timeline */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-4">Daily Flow — Timeline</h3>
        <div className="space-y-0">
          {timelineSteps.map((step, i) => (
            <div key={i} className="flex gap-4">
              {/* Timeline line */}
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${
                  step.role === 'manual' ? 'bg-orange-500/20 border-2 border-orange-500' : 'bg-dark-600 border border-dark-400'
                }`}>
                  {step.icon}
                </div>
                {i < timelineSteps.length - 1 && (
                  <div className={`w-0.5 h-full min-h-[20px] ${step.role === 'manual' ? 'bg-orange-500/30' : 'bg-dark-500'}`} />
                )}
              </div>
              {/* Content */}
              <div className="pb-4 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs text-gray-500 font-mono w-20">{step.time}</span>
                  <span className={`text-sm font-semibold ${step.role === 'manual' ? 'text-orange-400' : 'text-white'}`}>
                    {step.title}
                  </span>
                  {step.role === 'manual' && (
                    <span className="text-[9px] bg-orange-500/20 text-orange-400 px-1.5 py-0.5 rounded font-bold">YOU</span>
                  )}
                  {step.role === 'auto' && (
                    <span className="text-[9px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded font-bold">AUTO</span>
                  )}
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Equity Regime Types */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-1">Equity Market Regimes</h3>
        <p className="text-xs text-gray-500 mb-4">12 regime types detected from NIFTY trend + VIX + ADX + BB squeeze + RSI + calendar events</p>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-500">
                {['Regime', 'Condition', 'Strategies Selected'].map(h => (
                  <th key={h} className="text-left text-[10px] font-medium text-gray-500 uppercase px-3 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-xs">
              {[
                ['Bullish Trend', 'NIFTY above EMAs, ADX strong', 'Play 9 (Gap), Play 7 (ORB), Play 4 (Supertrend), Play 1 (EMA), Play 3 (VWAP)'],
                ['Bearish Trend', 'NIFTY below EMAs, ADX strong', 'Play 9 (Gap), Play 7 (ORB), Play 4 (Supertrend), Play 1 (EMA)'],
                ['Pullback in Uptrend', 'Bullish trend but retracing', 'Play 4 (Supertrend), Play 8 (RSI Divergence), Play 3 (VWAP), Play 6 (BB Contra)'],
                ['Bounce in Downtrend', 'Bearish trend but bouncing', 'Play 4 (Supertrend), Play 8 (RSI Divergence), Play 3 (VWAP), Play 6 (BB Contra)'],
                ['Sideways', 'No clear trend, range-bound', 'Play 5 (BB Squeeze), Play 8 (RSI Divergence), Play 6 (BB Contra)'],
                ['Reversal', 'Trend direction changing', 'Play 8 (RSI Divergence), Play 6 (BB Contra)'],
                ['Neutral', 'Mixed signals, no conviction', 'Play 9 (Gap), Play 7 (ORB), Play 4 (Supertrend), Play 8 (RSI Divergence), Play 6 (BB Contra)'],
                ['Squeeze', 'BB width compressed < 60% avg', 'Play 5 (BB Squeeze), Play 7 (ORB), Play 4 (Supertrend)'],
                ['Trend Exhaustion', 'Bullish but RSI > 70 (overextended)', 'Play 8 (RSI Divergence), Play 6 (BB Contra)'],
                ['Oversold Bounce', 'Bearish but RSI < 30 (oversold)', 'Play 8 (RSI Divergence), Play 3 (VWAP), Play 6 (BB Contra)'],
                ['Expiry Day', 'F&O weekly/monthly expiry', 'Play 4 (Supertrend), Play 6 (BB Contra) — conservative'],
                ['Pre-Holiday', 'Day before market holiday', 'Play 6 (BB Contra), Play 5 (BB Squeeze) — low risk only'],
              ].map((row, i) => (
                <tr key={i} className="border-b border-dark-600/30">
                  <td className="px-3 py-2 text-white font-medium">{row[0]}</td>
                  <td className="px-3 py-2 text-gray-400">{row[1]}</td>
                  <td className="px-3 py-2 text-orange-400">{row[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* What Auto-Tuner Adjusts */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-1">Auto-Tuner — What Gets Optimized</h3>
        <p className="text-xs text-gray-500 mb-4">Runs daily after square-off. Acts as a Senior Quantitative Trading Strategist.</p>
        <div className="space-y-3">
          {autoTuneParams.map((item, i) => (
            <div key={i} className="bg-dark-600/50 rounded-xl p-4 border border-dark-500/50">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-purple-400">{item.param}</span>
                <span className="text-[9px] text-gray-500 bg-dark-700 px-2 py-0.5 rounded">{item.frequency}</span>
              </div>
              <p className="text-xs text-gray-400 mb-1"><span className="text-gray-500">What:</span> {item.what}</p>
              <p className="text-xs text-gray-400 mb-1"><span className="text-gray-500">How:</span> {item.how}</p>
              <p className="text-xs text-gray-400"><span className="text-gray-500">Bounds:</span> <span className="text-emerald-400">{item.bounds}</span></p>
            </div>
          ))}
        </div>
      </div>

      {/* Day-over-Day Improvement Cycle */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-4">Day-over-Day Improvement Cycle</h3>
        <div className="grid grid-cols-5 gap-2 text-center">
          {['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5'].map((day, i) => (
            <div key={i} className="space-y-2">
              <div className={`rounded-xl p-3 border ${i === 0 ? 'bg-dark-600 border-dark-400' : 'bg-dark-600/50 border-dark-500/30'}`}>
                <p className="text-xs font-bold text-white">{day}</p>
                <p className="text-[9px] text-gray-400 mt-1">
                  {i === 0 && 'Baseline. No changes yet.'}
                  {i === 1 && 'Boosts updated. Best strategy prioritized.'}
                  {i === 2 && 'SL rate checked. May widen ATR.'}
                  {i === 3 && 'Volume filter checked. Trade count balanced.'}
                  {i === 4 && 'Full optimization cycle. System self-calibrated.'}
                </p>
              </div>
              {i < 4 && <div className="text-gray-500">→</div>}
            </div>
          ))}
        </div>
        <div className="mt-4 bg-dark-600/50 rounded-lg p-3 border border-emerald-500/20">
          <p className="text-xs text-emerald-400 font-semibold mb-1">What improves automatically each day:</p>
          <div className="grid grid-cols-2 gap-1 text-[10px] text-gray-400">
            <span>• Strategy that won → higher priority tomorrow</span>
            <span>• Strategy that lost → deprioritized tomorrow</span>
            <span>• SLs too tight → gradually widened</span>
            <span>• SLs too wide → gradually tightened</span>
            <span>• Too few signals → volume filter loosened</span>
            <span>• Too many bad signals → volume filter tightened</span>
          </div>
        </div>
      </div>

      {/* Safety Guardrails */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-3">Safety Guardrails</h3>
        <div className="grid grid-cols-2 gap-2">
          {safetyGuardrails.map((rule, i) => (
            <div key={i} className="flex items-start gap-2 bg-dark-600/50 rounded-lg px-3 py-2 border border-dark-500/30">
              <Shield size={12} className="text-emerald-400 flex-shrink-0 mt-0.5" />
              <span className="text-xs text-gray-400">{rule}</span>
            </div>
          ))}
        </div>
      </div>

      {/* QA Testing */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6">
        <h3 className="text-lg font-semibold text-white mb-3">Post-Fix QA Testing — 34 Automated Checks</h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-dark-600/50 rounded-lg p-3 border border-dark-500/30">
            <p className="text-xs font-semibold text-blue-400 mb-2">Module Imports (15)</p>
            <p className="text-[10px] text-gray-400">All 10 strategy files + 5 service files must import without errors after any parameter change.</p>
          </div>
          <div className="bg-dark-600/50 rounded-lg p-3 border border-dark-500/30">
            <p className="text-xs font-semibold text-purple-400 mb-2">Parameter Bounds (9)</p>
            <p className="text-[10px] text-gray-400">ATR mult (2), volume threshold (1), strategy boosts (6) — all must be within guardrail bounds.</p>
          </div>
          <div className="bg-dark-600/50 rounded-lg p-3 border border-dark-500/30">
            <p className="text-xs font-semibold text-emerald-400 mb-2">Functional Tests (7)</p>
            <p className="text-[10px] text-gray-400">Regime detection works, volume filters present in all 9 strategy files, conviction scoring intact.</p>
          </div>
        </div>
        <div className="mt-3 bg-red-500/10 rounded-lg p-3 border border-red-500/20">
          <p className="text-xs text-red-400 font-semibold">If ANY check fails → ALL changes auto-rolled back</p>
          <p className="text-[10px] text-gray-400 mt-1">System reverts to pre-tune parameters. Tomorrow trades with yesterday's known-good config. Failure logged for investigation.</p>
        </div>
      </div>
    </>
  )
}


/* ─── Tab: E2E Flow & Architecture ─── */
/* ─── Tab: Shortcuts ─── */
function ShortcutsTab() {
  const paperShortcuts = [
    { key: 'status', desc: 'All 6 paper engines + regime + P&L' },
    { key: 'trades', desc: 'Open paper positions across all engines' },
    { key: 'pnl', desc: "Today's paper P&L breakdown by engine" },
    { key: 'regime', desc: 'Market regime + VIX + ADX + strategies' },
    { key: 'monitor', desc: 'Daemon health check log (last 15 entries)' },
    { key: 'review', desc: 'Full day review + what worked + recommendations' },
    { key: 'history', desc: 'Last 7 days paper trade history' },
    { key: 'changelog', desc: 'Recent parameter changes by auto-tuner' },
    { key: 'start', desc: 'Start servers + all paper engines' },
    { key: 'stop', desc: 'Stop servers for the day' },
    { key: 'push', desc: 'Commit + push code to GitHub' },
  ]

  const liveShortcuts = [
    { key: 'live status', desc: 'All live engines + capital + positions' },
    { key: 'live trades', desc: 'Open REAL positions from Fyers' },
    { key: 'live pnl', desc: "Today's real P&L (Fyers source of truth)" },
    { key: 'live funds', desc: 'Fyers available balance + margin used' },
    { key: 'live orders', desc: 'Fyers order book (filled/pending/rejected)' },
    { key: 'live positions', desc: 'Fyers net positions with real P&L' },
    { key: 'capital', desc: 'Current capital + allocation across engines' },
    { key: 'scale', desc: 'Which engines are active based on capital' },
  ]

  const bothShortcuts = [
    { key: 'regime', desc: 'Current market regime (same for both modes)' },
    { key: 'monitor', desc: 'System health daemon (runs every 5 min)' },
    { key: 'review', desc: 'Combined paper + live day review' },
    { key: 'tracker', desc: 'Improvement tracker sidebar data' },
  ]

  return (
    <>
      <div className="bg-gradient-to-br from-blue-500/10 via-dark-700 to-purple-500/10 rounded-2xl border border-dark-500 p-6 mb-6">
        <h2 className="text-xl font-bold text-white mb-2">Claude CLI Shortcuts</h2>
        <p className="text-sm text-gray-400">Type these keywords in the Claude conversation to get instant system info.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Paper Shortcuts */}
        <div className="bg-dark-700 rounded-2xl border border-blue-500/20 p-5">
          <h3 className="text-sm font-bold text-blue-400 mb-3 flex items-center gap-2">
            <Monitor size={14} /> Paper Mode (Testing)
          </h3>
          <div className="space-y-2">
            {paperShortcuts.map((s, i) => (
              <div key={i} className="flex items-start gap-3">
                <code className="text-xs bg-dark-600 text-blue-300 px-2 py-1 rounded font-mono whitespace-nowrap">{s.key}</code>
                <span className="text-xs text-gray-400 pt-0.5">{s.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Live Shortcuts */}
        <div className="bg-dark-700 rounded-2xl border border-orange-500/20 p-5">
          <h3 className="text-sm font-bold text-orange-400 mb-3 flex items-center gap-2">
            <Zap size={14} /> Live Mode (From Mar 25)
          </h3>
          <div className="space-y-2">
            {liveShortcuts.map((s, i) => (
              <div key={i} className="flex items-start gap-3">
                <code className="text-xs bg-dark-600 text-orange-300 px-2 py-1 rounded font-mono whitespace-nowrap">{s.key}</code>
                <span className="text-xs text-gray-400 pt-0.5">{s.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Both Modes */}
      <div className="bg-dark-700 rounded-2xl border border-purple-500/20 p-5 mt-6">
        <h3 className="text-sm font-bold text-purple-400 mb-3 flex items-center gap-2">
          <Settings size={14} /> Both Modes
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {bothShortcuts.map((s, i) => (
            <div key={i} className="flex items-start gap-3">
              <code className="text-xs bg-dark-600 text-purple-300 px-2 py-1 rounded font-mono whitespace-nowrap">{s.key}</code>
              <span className="text-xs text-gray-400 pt-0.5">{s.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Capital Allocation */}
      <div className="bg-dark-700 rounded-2xl border border-emerald-500/20 p-5 mt-6">
        <h3 className="text-sm font-bold text-emerald-400 mb-3">Live Capital Auto-Allocation</h3>
        <p className="text-xs text-gray-400 mb-3">System auto-detects available capital from Fyers and allocates engines accordingly:</p>
        <div className="space-y-1.5">
          {[
            { cap: '< ₹1L', engines: 'Options Intraday only', alloc: '100% options' },
            { cap: '₹1L – ₹2.5L', engines: 'Options + Equity Intraday', alloc: '50/50 split' },
            { cap: '₹2.5L – ₹5L', engines: '+ Equity Swing + Options Swing', alloc: '4 engines' },
            { cap: '₹5L – ₹10L', engines: '+ Futures Intraday', alloc: '5 engines' },
            { cap: '₹10L+', engines: 'All 6 engines', alloc: 'Full deployment' },
          ].map((r, i) => (
            <div key={i} className="flex items-center justify-between bg-dark-600/50 rounded-lg px-3 py-2 border border-dark-500/30 text-xs">
              <span className="text-emerald-400 font-medium w-28">{r.cap}</span>
              <span className="text-white flex-1">{r.engines}</span>
              <span className="text-gray-500">{r.alloc}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}


function E2EFlowTab() {
  const [registry, setRegistry] = useState(null)
  const [changelog, setChangelog] = useState([])

  useEffect(() => {
    fetch('http://localhost:8001/api/tracking/registry').then(r => r.json()).then(setRegistry).catch(() => {})
    fetch('http://localhost:8001/api/tracking/changelog').then(r => r.json()).then(d => setChangelog(d.changes || [])).catch(() => {})
  }, [])

  // Extract live values from registry
  const risk = registry?.global_config?.risk || {}
  const liveParams = {
    'Position Check': `Every ${risk.intraday_position_check_interval_sec || 20}s (equity), ${risk.options_position_check_interval_sec || 15}s (options)`,
    'Futures Risk': `${((risk.futures_risk_per_trade_pct || 0.02) * 100).toFixed(0)}% per trade, ${risk.futures_daily_loss_limit_pct || 5}% daily loss limit`,
    'ATR Stop Loss': `${registry?.candlestick_definitions?.atr_sl_default_mult || 2.5}x ATR, ${((registry?.candlestick_definitions?.atr_sl_default_min_pct || 0.012) * 100).toFixed(1)}% min floor`,
    'Iron Condor': registry?.options?.strategies?.iron_condor?.vix_gate || 'Blocked when VIX > 16',
    'Data Source': 'Fyers real-time (yfinance fallback)',
  }

  // Count recent auto-tune changes
  const recentAutoTunes = changelog.filter(c => c.type === 'AUTO_TUNE').length
  const lastUpdate = registry?._meta?.last_updated || 'unknown'

  return (
    <>
      {/* Live params notice */}
      {registry && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-2 mb-4 flex items-center justify-between">
          <span className="text-xs text-emerald-400">Parameters fetched live from backend registry (v{registry._meta?.version || '?'})</span>
          <span className="text-[10px] text-gray-500">Last updated: {lastUpdate} | {recentAutoTunes} auto-tunes logged</span>
        </div>
      )}

      {/* Architecture Overview */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-4">System Architecture</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-dark-600/50 rounded-xl p-4 border border-blue-500/20">
            <p className="text-sm font-bold text-blue-400 mb-2">Frontend</p>
            <p className="text-xs text-gray-400">React + Vite + Tailwind</p>
            <p className="text-xs text-gray-500 mt-1">Port 3000 | Dashboard, Trading Pages, Tracker Sidebar</p>
          </div>
          <div className="bg-dark-600/50 rounded-xl p-4 border border-orange-500/20">
            <p className="text-sm font-bold text-orange-400 mb-2">Backend</p>
            <p className="text-xs text-gray-400">FastAPI + Python</p>
            <p className="text-xs text-gray-500 mt-1">Port 8001 | 12 Engines, Scanner, Regime Detection, Auto-Tuner</p>
          </div>
          <div className="bg-dark-600/50 rounded-xl p-4 border border-emerald-500/20">
            <p className="text-sm font-bold text-emerald-400 mb-2">Broker</p>
            <p className="text-xs text-gray-400">Fyers API v3</p>
            <p className="text-xs text-gray-500 mt-1">Real-time data, Order execution, Positions, Funds</p>
          </div>
        </div>
      </div>

      {/* Data Flow */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-4">Data Flow — Scan to Trade</h3>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
            <p className="font-semibold text-emerald-400">Fyers OHLCV</p>
            <p className="text-[9px] text-gray-500">Real-time candles (yfinance fallback)</p>
          </div>
          <span className="text-dark-400 text-lg">→</span>
          <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg px-3 py-2">
            <p className="font-semibold text-purple-400">Regime Detector</p>
            <p className="text-[9px] text-gray-500">NIFTY + VIX + ADX + Intraday direction</p>
          </div>
          <span className="text-dark-400 text-lg">→</span>
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-2">
            <p className="font-semibold text-blue-400">Strategy Scanner</p>
            <p className="text-[9px] text-gray-500">9 equity + 8 futures strategies</p>
          </div>
          <span className="text-dark-400 text-lg">→</span>
          <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">
            <p className="font-semibold text-yellow-400">Volume Filter</p>
            <p className="text-[9px] text-gray-500">Reject low-volume noise</p>
          </div>
          <span className="text-dark-400 text-lg">→</span>
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg px-3 py-2">
            <p className="font-semibold text-orange-400">Conviction Ranking</p>
            <p className="text-[9px] text-gray-500">Score by vol + price + strategy boost</p>
          </div>
          <span className="text-dark-400 text-lg">→</span>
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            <p className="font-semibold text-red-400">Order Placement</p>
            <p className="text-[9px] text-gray-500">Fyers API (live) or Virtual (paper)</p>
          </div>
        </div>
      </div>

      {/* 12 Engines Grid */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <h3 className="text-lg font-semibold text-white mb-4">12 Trading Engines</h3>
        <div className="grid grid-cols-4 gap-3">
          <div className="text-center text-xs text-gray-500 font-semibold pb-2"></div>
          <div className="text-center text-xs text-orange-400 font-semibold pb-2">Equity</div>
          <div className="text-center text-xs text-violet-400 font-semibold pb-2">Options</div>
          <div className="text-center text-xs text-amber-400 font-semibold pb-2">Futures</div>

          {['Intraday Live', 'Intraday Paper', 'Swing Live', 'Swing Paper'].map((row, ri) => (
            <React.Fragment key={ri}>
              <div className="text-xs text-gray-400 flex items-center">{row}</div>
              {['equity', 'options', 'futures'].map((col, ci) => {
                const configs = {
                  'Intraday Live-equity': { time: '10:30 AM', max: 6 },
                  'Intraday Paper-equity': { time: '10:30 AM', max: 10 },
                  'Swing Live-equity': { time: '9:20 AM', max: 1 },
                  'Swing Paper-equity': { time: '9:20 AM', max: 5 },
                  'Intraday Live-options': { time: '10:00 AM', max: 4 },
                  'Intraday Paper-options': { time: '10:00 AM', max: 3 },
                  'Swing Live-options': { time: 'Every 4h', max: 2 },
                  'Swing Paper-options': { time: 'Every 4h', max: 2 },
                  'Intraday Live-futures': { time: '11:00 AM', max: 4 },
                  'Intraday Paper-futures': { time: '11:00 AM', max: 8 },
                  'Swing Live-futures': { time: 'Every 4h', max: 2 },
                  'Swing Paper-futures': { time: 'Every 4h', max: 5 },
                }
                const c = configs[`${row}-${col}`] || {}
                return (
                  <div key={ci} className="bg-dark-600/50 rounded-lg p-2 text-center border border-dark-500/30">
                    <p className="text-[10px] text-white">{c.time}</p>
                    <p className="text-[9px] text-gray-500">Max {c.max} pos</p>
                  </div>
                )
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Key Rules — live values from registry */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-white">Key Rules & Parameters</h3>
          <span className="text-[9px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">LIVE from registry</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            { label: 'Market Hours', value: '9:15 AM - 3:30 PM IST (Mon-Fri)' },
            { label: 'Equity Orders', value: registry?.global_config?.timing?.intraday_order_start ? `${registry.global_config.timing.intraday_order_start} - ${registry.global_config.timing.intraday_order_cutoff}` : '10:30 AM - 2:00 PM' },
            { label: 'Futures Orders', value: '11:00 AM - 2:00 PM' },
            { label: 'Options Orders', value: registry?.global_config?.timing?.options_order_start ? `${registry.global_config.timing.options_order_start} - ${registry.global_config.timing.options_order_cutoff}` : '10:00 AM - 2:00 PM' },
            { label: 'Equity Square-off', value: registry?.global_config?.timing?.intraday_squareoff || '3:15 PM' },
            { label: 'Options Square-off', value: registry?.global_config?.timing?.options_squareoff || '3:00 PM' },
            { label: 'Position Check', value: liveParams['Position Check'] },
            { label: 'Futures Risk', value: liveParams['Futures Risk'], live: true },
            { label: 'ATR Stop Loss', value: liveParams['ATR Stop Loss'], live: true },
            { label: 'Volume Filter', value: '> 1.3x SMA20 required' },
            { label: 'Signal Ranking', value: registry?.signal_ranking?.method || 'Conviction score' },
            { label: 'Scan Universe', value: 'Nifty 500 (equity), F&O stocks (futures)' },
            { label: 'Price Filter', value: registry?.global_config?.price_filters ? `₹${registry.global_config.price_filters.intraday_min}-₹${registry.global_config.price_filters.intraday_max.toLocaleString()} (intraday)` : '₹50-₹5,000' },
            { label: 'Swing Retry', value: '9:20 AM + every 2 hours' },
            { label: 'Max Orders/Scan', value: '2 (staggered filling)' },
            { label: 'OI Filter (Futures)', value: 'Hard — blocks counter-sentiment trades' },
            { label: 'Iron Condor', value: liveParams['Iron Condor'], live: true },
            { label: 'Data Source', value: liveParams['Data Source'] },
            { label: 'Trailing SL', value: 'Activates at +1%, trails 50% of max profit' },
            { label: 'Drawdown Breaker', value: '15% loss over 5 days → 1 order/scan max' },
            { label: 'Fyers Health', value: 'Auto-reconnect every 5 min (live traders)' },
          ].map((item, i) => (
            <div key={i} className={`flex items-center justify-between rounded-lg px-3 py-2 border ${
              item.live ? 'bg-purple-500/5 border-purple-500/20' : 'bg-dark-600/50 border-dark-500/30'
            }`}>
              <span className="text-gray-400">{item.label}</span>
              <span className="text-white font-medium flex items-center gap-1">
                {item.value}
                {item.live && <span className="text-[8px] text-purple-400">●</span>}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[9px] text-gray-600 mt-2"><span className="text-purple-400">●</span> = auto-tunable parameters (adjusted daily by system)</p>
      </div>

      {/* Getting Started */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-6">
        <h3 className="text-lg font-semibold text-white mb-3">Quick Start</h3>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-orange-500/20 border border-orange-500/30 flex items-center justify-center text-orange-400 text-xs font-bold flex-shrink-0">1</div>
            <p className="text-xs text-gray-400">Start backend: cd backend && source venv/bin/activate && python main.py</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-400 text-xs font-bold flex-shrink-0">2</div>
            <p className="text-xs text-gray-400">Start frontend: cd frontend && npm run dev</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-xs font-bold flex-shrink-0">3</div>
            <p className="text-xs text-gray-400">Open http://localhost:3000 → Login to Fyers (auto headless login)</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 text-xs font-bold flex-shrink-0">4</div>
            <p className="text-xs text-gray-400">9:15 AM — Press Start on all 6 engines (9 equity + 8 futures + 6 options strategies). Close browser. Done.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-pink-500/20 border border-pink-500/30 flex items-center justify-center text-pink-400 text-xs font-bold flex-shrink-0">5</div>
            <p className="text-xs text-gray-400">3:30 PM — Check Tracker sidebar for daily report + improvements</p>
          </div>
        </div>
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
    { label: 'Intraday Orders', value: '10:30 AM - 2:00 PM (equity) / 11:00 AM - 2:00 PM (futures)', icon: Clock },
    { label: 'Auto Square-Off', value: '3:15 PM (intraday only)', icon: Square },
    { label: 'Swing Scan', value: '9:20 AM + retry every 2 hours', icon: Search },
    { label: 'Swing Direction', value: 'BUY only (no CNC short selling)', icon: TrendingUp },
    { label: 'Swing Nifty Filter', value: 'Blocks BUY only when Nifty < 50 SMA', icon: Shield },
    { label: 'Intraday Price Range', value: 'Rs 50 - Rs 5,000', icon: IndianRupee },
    { label: 'Swing Price Range', value: 'Rs 100 - Rs 1,500', icon: IndianRupee },
    { label: 'Intraday Product', value: 'INTRADAY (MIS)', icon: Zap },
    { label: 'Swing Product', value: 'CNC (delivery, carries overnight)', icon: Repeat },
    { label: 'Futures Universe', value: '~180 NSE F&O stocks with lot sizes', icon: BarChart3 },
    { label: 'Futures Risk/Trade', value: '2% of capital (margin-based lots)', icon: Shield },
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
      case 'strategies': return <StrategiesTab />
      case 'options': return <OptionsTab />
      case 'futures': return <FuturesTab />
      case 'pages': return <AppPagesTab />
      case 'shortcuts': return <ShortcutsTab />
      case 'auto-system': return <AutoSystemTab />
      case 'e2e-flow': return <E2EFlowTab />
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
