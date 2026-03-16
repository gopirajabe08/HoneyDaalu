import React, { useState } from 'react'
import { FlaskConical, Play, Loader2, TrendingUp, TrendingDown, Minus, Calendar, Clock } from 'lucide-react'
import { strategies } from '../data/mockData'
import { runBacktest } from '../services/api'

export default function BacktestPage({ capital }) {
  const [selectedStrategy, setSelectedStrategy] = useState('')
  const [selectedTimeframe, setSelectedTimeframe] = useState('')
  const [btCapital, setBtCapital] = useState(capital)
  const [selectedDate, setSelectedDate] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const strat = strategies.find(s => s.id === selectedStrategy)
  const timeframes = strat?.timeframes || []

  function handleStrategyChange(id) {
    setSelectedStrategy(id)
    setSelectedTimeframe('')
    setResult(null)
    setError('')
    const s = strategies.find(st => st.id === id)
    if (s && s.timeframes.length > 0) {
      setSelectedTimeframe(s.timeframes[0])
    }
  }

  async function handleRun() {
    if (!selectedStrategy || !selectedTimeframe) return
    setRunning(true)
    setResult(null)
    setError('')
    try {
      const data = await runBacktest(selectedStrategy, selectedTimeframe, btCapital, selectedDate || null)
      if (data.error) {
        setError(data.error)
      } else {
        setResult(data)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  const summary = result?.summary

  return (
    <div>
      <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <FlaskConical size={20} className="text-orange-400" />
        Strategy Backtester
        <span className="text-xs text-gray-400 font-normal ml-1">Nifty 500 — Historical Simulation</span>
      </h2>

      {/* Controls */}
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5 mb-5">
        <div className="flex flex-wrap gap-4 items-end">
          {/* Strategy */}
          <div className="flex-1 min-w-[200px]">
            <label className="text-[10px] text-gray-500 uppercase font-medium mb-1.5 block">Strategy</label>
            <select
              value={selectedStrategy}
              onChange={e => handleStrategyChange(e.target.value)}
              className="w-full bg-dark-600 border border-dark-500 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-orange-500/50"
            >
              <option value="">Select strategy...</option>
              {strategies.map(s => (
                <option key={s.id} value={s.id}>{s.shortName}: {s.name}</option>
              ))}
            </select>
          </div>

          {/* Timeframe */}
          <div className="w-[140px]">
            <label className="text-[10px] text-gray-500 uppercase font-medium mb-1.5 block">Timeframe</label>
            <div className="flex gap-1.5">
              {timeframes.map(tf => (
                <button
                  key={tf}
                  onClick={() => setSelectedTimeframe(tf)}
                  className={`flex-1 px-2 py-2.5 rounded-xl text-xs font-medium transition-all ${
                    selectedTimeframe === tf
                      ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                      : 'bg-dark-600 text-gray-500 border border-dark-500 hover:text-gray-300'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Capital */}
          <div className="w-[140px]">
            <label className="text-[10px] text-gray-500 uppercase font-medium mb-1.5 block">Capital</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">{'\u20B9'}</span>
              <input
                type="number"
                value={btCapital}
                onChange={e => setBtCapital(Number(e.target.value) || 0)}
                className="w-full bg-dark-600 border border-dark-500 rounded-xl pl-7 pr-3 py-2.5 text-sm text-white focus:outline-none focus:border-orange-500/50 tabular-nums"
              />
            </div>
          </div>

          {/* Date */}
          <div className="w-[180px]">
            <label className="text-[10px] text-gray-500 uppercase font-medium mb-1.5 block">Date (optional)</label>
            <input
              type="date"
              value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)}
              className="w-full bg-dark-600 border border-dark-500 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-orange-500/50 [color-scheme:dark]"
            />
          </div>

          {/* Run */}
          <button
            onClick={handleRun}
            disabled={running || !selectedStrategy || !selectedTimeframe}
            className="bg-gradient-to-r from-orange-500 to-pink-500 text-white rounded-xl px-6 py-2.5 text-sm font-semibold flex items-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {running ? (
              <><Loader2 size={16} className="animate-spin" /> Running...</>
            ) : (
              <><Play size={16} /> Run Backtest</>
            )}
          </button>
        </div>

        {!selectedDate && selectedStrategy && (
          <p className="text-[10px] text-gray-600 mt-2">No date selected — will use last trading day</p>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-5">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Loading */}
      {running && (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-10 flex flex-col items-center gap-3">
          <Loader2 size={32} className="animate-spin text-orange-400" />
          <p className="text-sm text-gray-400">Fetching data & simulating trades for ~500 stocks...</p>
          <p className="text-[10px] text-gray-600">This may take 1-2 minutes</p>
        </div>
      )}

      {/* Results */}
      {result && !running && (
        <>
          {/* Header */}
          <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5 mb-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-white">{result.strategy_name}</h3>
                <p className="text-[10px] text-gray-500 mt-0.5">
                  <Calendar size={10} className="inline mr-1" />
                  {result.date_display} &bull; {result.timeframe} ({result.mode}) &bull; {result.stocks_fetched} stocks &bull; {result.fetch_time}s fetch
                </p>
              </div>
              <div className={`text-2xl font-bold tabular-nums ${summary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {summary.total_pnl >= 0 ? '+' : ''}{'\u20B9'}{summary.total_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              <Stat label="Trades" value={summary.total_trades} />
              <Stat label="Winners" value={summary.winners} color="text-green-400" />
              <Stat label="Losers" value={summary.losers} color="text-red-400" />
              <Stat label="Win Rate" value={`${summary.win_rate}%`} color={summary.win_rate >= 50 ? 'text-green-400' : 'text-yellow-400'} />
              <Stat label="ROI" value={`${summary.roi >= 0 ? '+' : ''}${summary.roi}%`} color={summary.roi >= 0 ? 'text-green-400' : 'text-red-400'} />
              <Stat label="Profit Factor" value={summary.profit_factor || '—'} color={summary.profit_factor >= 1.5 ? 'text-green-400' : summary.profit_factor >= 1 ? 'text-yellow-400' : 'text-red-400'} />
              <Stat label="Avg P&L" value={`\u20B9${summary.avg_trade_pnl.toLocaleString('en-IN')}`} color={summary.avg_trade_pnl >= 0 ? 'text-green-400' : 'text-red-400'} />
            </div>
          </div>

          {/* Trade Table */}
          {result.trades.length > 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 overflow-hidden">
              <div className="px-5 py-3 border-b border-dark-500">
                <h4 className="text-xs font-semibold text-white">Trade Details ({result.trades.length})</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="bg-dark-600 text-gray-500 uppercase">
                      <th className="text-left px-3 py-2 font-medium">Symbol</th>
                      <th className="text-center px-2 py-2 font-medium">Type</th>
                      <th className="text-center px-2 py-2 font-medium">Scan</th>
                      <th className="text-right px-2 py-2 font-medium">Entry</th>
                      <th className="text-right px-2 py-2 font-medium">SL</th>
                      <th className="text-right px-2 py-2 font-medium">Target</th>
                      <th className="text-right px-2 py-2 font-medium">Exit</th>
                      <th className="text-center px-2 py-2 font-medium">R:R</th>
                      <th className="text-center px-2 py-2 font-medium">Outcome</th>
                      <th className="text-right px-2 py-2 font-medium">Qty</th>
                      <th className="text-right px-3 py-2 font-medium">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <tr key={i} className="border-t border-dark-600 hover:bg-dark-600/50 transition-colors">
                        <td className="px-3 py-2 font-medium text-white">{t.symbol}</td>
                        <td className="text-center px-2 py-2">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
                            t.signal_type === 'BUY' ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'
                          }`}>
                            {t.signal_type}
                          </span>
                        </td>
                        <td className="text-center px-2 py-2 text-gray-400">{t.scan_time}</td>
                        <td className="text-right px-2 py-2 text-gray-300 tabular-nums">{'\u20B9'}{t.entry_price.toFixed(2)}</td>
                        <td className="text-right px-2 py-2 text-red-400/70 tabular-nums">{'\u20B9'}{t.stop_loss.toFixed(2)}</td>
                        <td className="text-right px-2 py-2 text-green-400/70 tabular-nums">{'\u20B9'}{t.target.toFixed(2)}</td>
                        <td className="text-right px-2 py-2 text-gray-300 tabular-nums">{'\u20B9'}{t.exit_price.toFixed(2)}</td>
                        <td className="text-center px-2 py-2 text-gray-500">{t.risk_reward}</td>
                        <td className="text-center px-2 py-2">
                          <OutcomeBadge outcome={t.outcome} />
                        </td>
                        <td className="text-right px-2 py-2 text-gray-400 tabular-nums">{t.qty}</td>
                        <td className={`text-right px-3 py-2 font-semibold tabular-nums ${
                          t.total_pnl > 0 ? 'text-green-400' : t.total_pnl < 0 ? 'text-red-400' : 'text-gray-500'
                        }`}>
                          {t.total_pnl >= 0 ? '+' : ''}{'\u20B9'}{t.total_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-dark-500 bg-dark-600">
                      <td colSpan={10} className="px-3 py-2.5 text-xs font-semibold text-gray-400 text-right">
                        Total P&L
                      </td>
                      <td className={`px-3 py-2.5 text-right text-sm font-bold tabular-nums ${
                        summary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {summary.total_pnl >= 0 ? '+' : ''}{'\u20B9'}{summary.total_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}

          {/* No trades message */}
          {result.trades.length === 0 && (
            <div className="bg-dark-700 rounded-2xl border border-dark-500 p-8 text-center">
              <Minus size={32} className="mx-auto text-gray-600 mb-2" />
              <p className="text-sm text-gray-400">No trades executed on this date</p>
              <p className="text-[10px] text-gray-600 mt-1">
                {result.total_signals} signal(s) found across {result.scan_windows} scan windows
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-dark-600 rounded-xl px-3 py-2.5 text-center">
      <p className={`text-sm font-semibold tabular-nums ${color}`}>{value}</p>
      <p className="text-[9px] text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

function OutcomeBadge({ outcome }) {
  const styles = {
    TARGET_HIT: 'bg-green-500/15 text-green-400',
    SL_HIT: 'bg-red-500/15 text-red-400',
    EOD_SQUAREOFF: 'bg-yellow-500/15 text-yellow-400',
  }
  const labels = {
    TARGET_HIT: 'Target',
    SL_HIT: 'SL Hit',
    EOD_SQUAREOFF: 'EOD Exit',
  }
  const style = styles[outcome] || 'bg-gray-500/15 text-gray-400'
  const label = labels[outcome] || outcome.replace(/_/g, ' ')
  return (
    <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${style}`}>
      {label}
    </span>
  )
}
