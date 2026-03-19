import React, { useState, useEffect, useCallback } from 'react'

const API = 'http://localhost:8001'

export default function ImprovementTracker() {
  const [isOpen, setIsOpen] = useState(false)
  const [reports, setReports] = useState([])
  const [changelog, setChangelog] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [reportsRes, changelogRes] = await Promise.all([
        fetch(`${API}/api/tracking/recent?days=7`).then(r => r.json()),
        fetch(`${API}/api/tracking/changelog`).then(r => r.json()),
      ])
      setReports(Array.isArray(reportsRes) ? reportsRes : [])
      setChangelog(changelogRes?.changes || [])
    } catch (e) {
      console.error('Tracker fetch error:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    if (isOpen) fetchData()
  }, [isOpen, fetchData])

  // Auto-refresh every 5 minutes when open
  useEffect(() => {
    if (!isOpen) return
    const interval = setInterval(fetchData, 300000)
    return () => clearInterval(interval)
  }, [isOpen, fetchData])

  const recentChanges = changelog.filter(c => c.id).slice(-8).reverse()

  // Compute day-over-day improvement
  const dailyStats = reports.map(r => {
    const strats = r.strategy_performance || {}
    let totalTrades = 0, wins = 0, totalPnl = 0, totalExpectancy = 0, stratCount = 0
    Object.values(strats).forEach(s => {
      totalTrades += s.trades || 0
      wins += s.wins || 0
      totalPnl += s.net_pnl || 0
      if (s.expectancy_per_trade !== undefined) {
        totalExpectancy += s.expectancy_per_trade
        stratCount++
      }
    })
    return {
      date: r.date,
      trades: totalTrades,
      wins,
      winRate: totalTrades > 0 ? Math.round(wins / totalTrades * 100) : 0,
      pnl: Math.round(totalPnl),
      avgExpectancy: stratCount > 0 ? Math.round(totalExpectancy / stratCount) : 0,
      insights: r.auto_insights || [],
      recommendations: r.recommendations || [],
      changesApplied: r.parameter_changes_today || [],
      best: r.best_trade || {},
      worst: r.worst_trade || {},
    }
  })

  return (
    <>
      {/* Toggle button — fixed right edge */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed top-1/2 -translate-y-1/2 z-50 transition-all duration-300 ${
          isOpen ? 'right-[340px]' : 'right-0'
        }`}
        title="Strategy Improvement Tracker"
      >
        <div className="bg-orange-500/90 hover:bg-orange-400 text-white px-1.5 py-4 rounded-l-lg shadow-lg cursor-pointer">
          <span className="text-xs font-bold writing-vertical" style={{ writingMode: 'vertical-rl' }}>
            {isOpen ? '✕ CLOSE' : '📊 TRACKER'}
          </span>
        </div>
      </button>

      {/* Sidebar panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[340px] bg-dark-800 border-l border-dark-500 z-40
          transform transition-transform duration-300 overflow-y-auto
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <div className="p-4 space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-orange-400">Improvement Tracker</h2>
            <button
              onClick={fetchData}
              className="text-xs text-dark-300 hover:text-white px-2 py-1 rounded bg-dark-600 hover:bg-dark-500"
            >
              {loading ? '...' : 'Refresh'}
            </button>
          </div>

          {/* Day-by-Day Performance */}
          <Section title="Day-by-Day Performance">
            {dailyStats.length === 0 ? (
              <p className="text-dark-300 text-xs">No reports yet. Generate after market close.</p>
            ) : (
              <div className="space-y-2">
                {dailyStats.map((day, i) => {
                  const prev = dailyStats[i + 1]
                  const pnlDelta = prev ? day.pnl - prev.pnl : null
                  const wrDelta = prev ? day.winRate - prev.winRate : null
                  return (
                    <div key={day.date} className={`p-3 rounded-xl border ${
                      i === 0 ? 'bg-dark-600/50 border-orange-500/30' : 'bg-dark-700/50 border-dark-500/30'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold text-white">
                          {i === 0 ? '📅 Today' : formatDate(day.date)}
                        </span>
                        <span className={`text-sm font-bold ${day.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          ₹{day.pnl.toLocaleString('en-IN')}
                        </span>
                      </div>
                      <div className="flex gap-3 text-xs text-dark-200">
                        <span>{day.trades} trades</span>
                        <span>Win: {day.winRate}%
                          {wrDelta !== null && (
                            <span className={wrDelta >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                              {' '}({wrDelta >= 0 ? '+' : ''}{wrDelta}%)
                            </span>
                          )}
                        </span>
                        <span>Exp: ₹{day.avgExpectancy}/trade</span>
                      </div>
                      {pnlDelta !== null && (
                        <div className={`text-xs mt-1 ${pnlDelta >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {pnlDelta >= 0 ? '▲' : '▼'} ₹{Math.abs(pnlDelta).toLocaleString('en-IN')} vs prev day
                        </div>
                      )}
                      {/* Best / Worst */}
                      {day.best?.symbol && (
                        <div className="text-xs mt-1.5 text-dark-200">
                          <span className="text-emerald-400">Best:</span> {day.best.symbol} ({day.best.strategy}) +₹{Math.round(day.best.pnl || 0)}
                        </div>
                      )}
                      {day.worst?.symbol && (
                        <div className="text-xs text-dark-200">
                          <span className="text-red-400">Worst:</span> {day.worst.symbol} ({day.worst.strategy}) ₹{Math.round(day.worst.pnl || 0)}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Section>

          {/* Trend Arrow */}
          {dailyStats.length >= 2 && (
            <Section title="Trend">
              <TrendIndicator stats={dailyStats} />
            </Section>
          )}

          {/* Auto Insights (today) */}
          {dailyStats[0]?.insights?.length > 0 && (
            <Section title="Today's Insights">
              <div className="space-y-1.5">
                {dailyStats[0].insights.map((insight, i) => (
                  <div key={i} className="text-xs leading-relaxed text-dark-200 bg-dark-700/50 rounded-lg px-3 py-2 border border-dark-500/30">
                    {insight}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Recommendations (auto-generated after square-off) */}
          {dailyStats[0]?.recommendations?.length > 0 && (
            <Section title="Recommendations">
              <div className="space-y-2">
                {dailyStats[0].recommendations.map((rec, i) => {
                  const colors = {
                    positive: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', icon: '✅', title: 'text-emerald-400' },
                    negative: { bg: 'bg-red-500/10', border: 'border-red-500/20', icon: '🔴', title: 'text-red-400' },
                    warning: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', icon: '⚠️', title: 'text-yellow-400' },
                    info: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', icon: 'ℹ️', title: 'text-blue-400' },
                  }
                  const c = colors[rec.type] || colors.info
                  return (
                    <div key={i} className={`${c.bg} ${c.border} border rounded-lg p-2.5`}>
                      <div className="flex items-start gap-2">
                        <span className="text-xs">{c.icon}</span>
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs font-semibold ${c.title}`}>{rec.title}</p>
                          <p className="text-[10px] text-dark-300 mt-0.5 leading-relaxed">{rec.detail}</p>
                          {rec.action && rec.action !== 'none' && (
                            <p className="text-[10px] text-dark-400 mt-1 italic">Action: {rec.action}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </Section>
          )}

          {/* Recent Parameter Changes */}
          <Section title="Recent Changes">
            {recentChanges.length === 0 ? (
              <p className="text-dark-300 text-xs">No parameter changes yet.</p>
            ) : (
              <div className="space-y-2">
                {recentChanges.map((change, i) => (
                  <div key={i} className="bg-dark-700/50 border border-dark-500/30 rounded-lg p-2.5">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        change.id?.startsWith('P0') ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>
                        {change.id}
                      </span>
                      <span className="text-xs text-dark-200 truncate">{change.parameter || change.type}</span>
                    </div>
                    {change.before !== undefined && change.after !== undefined && (
                      <div className="text-[11px] text-dark-300 flex gap-1 items-center">
                        <span className="text-red-400 line-through">
                          {typeof change.before === 'object' ? JSON.stringify(change.before) : String(change.before)}
                        </span>
                        <span className="text-dark-400">→</span>
                        <span className="text-emerald-400 font-medium">
                          {typeof change.after === 'object' ? JSON.stringify(change.after) : String(change.after)}
                        </span>
                      </div>
                    )}
                    <p className="text-[10px] text-dark-400 mt-1 leading-snug">{change.reason?.slice(0, 120)}{change.reason?.length > 120 ? '...' : ''}</p>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* Auto-Tune Status */}
          <Section title="Auto-Tuner">
            <p className="text-[10px] text-dark-400 mb-2">
              Runs after square-off. Adjusts strategy priority based on rolling performance. Flags SL/volume/regime issues for review.
            </p>
            <AutoTuneButton onCompleted={fetchData} />
          </Section>

          {/* Generate Report Button */}
          <GenerateButton onGenerated={fetchData} />
        </div>
      </div>
    </>
  )
}


function Section({ title, children }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-dark-300 uppercase tracking-wider mb-2">{title}</h3>
      {children}
    </div>
  )
}


function TrendIndicator({ stats }) {
  if (stats.length < 2) return null
  const today = stats[0]
  const yesterday = stats[1]

  const metrics = [
    { label: 'Win Rate', current: today.winRate, prev: yesterday.winRate, unit: '%', better: 'higher' },
    { label: 'P&L', current: today.pnl, prev: yesterday.pnl, unit: '₹', better: 'higher' },
    { label: 'Expectancy', current: today.avgExpectancy, prev: yesterday.avgExpectancy, unit: '₹', better: 'higher' },
    { label: 'Trades', current: today.trades, prev: yesterday.trades, unit: '', better: 'neutral' },
  ]

  return (
    <div className="grid grid-cols-2 gap-2">
      {metrics.map(m => {
        const delta = m.current - m.prev
        const improved = m.better === 'higher' ? delta > 0 : m.better === 'lower' ? delta < 0 : true
        return (
          <div key={m.label} className="bg-dark-700/50 border border-dark-500/30 rounded-lg p-2 text-center">
            <div className="text-[10px] text-dark-400 uppercase">{m.label}</div>
            <div className={`text-sm font-bold ${improved ? 'text-emerald-400' : delta < 0 ? 'text-red-400' : 'text-white'}`}>
              {m.unit === '₹' ? `₹${m.current.toLocaleString('en-IN')}` : `${m.current}${m.unit}`}
            </div>
            {delta !== 0 && (
              <div className={`text-[10px] ${improved ? 'text-emerald-400' : 'text-red-400'}`}>
                {delta > 0 ? '▲' : '▼'} {m.unit === '₹' ? `₹${Math.abs(delta).toLocaleString('en-IN')}` : `${Math.abs(delta)}${m.unit}`}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}


function GenerateButton({ onGenerated }) {
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState(null)

  const generate = async () => {
    setGenerating(true)
    setResult(null)
    try {
      const res = await fetch(`${API}/api/tracking/generate`, { method: 'POST' })
      const data = await res.json()
      setResult({ ok: true, trades: data.total_trades, pnl: data.total_net_pnl })
      onGenerated()
    } catch (e) {
      setResult({ ok: false, error: e.message })
    }
    setGenerating(false)
  }

  return (
    <div className="pt-2 border-t border-dark-600">
      <button
        onClick={generate}
        disabled={generating}
        className="w-full py-2 rounded-lg text-sm font-medium bg-orange-500/20 text-orange-400 hover:bg-orange-500/30 disabled:opacity-50 transition-colors"
      >
        {generating ? 'Generating...' : '📊 Generate Daily Report'}
      </button>
      {result && (
        <div className={`text-xs mt-2 text-center ${result.ok ? 'text-emerald-400' : 'text-red-400'}`}>
          {result.ok ? `Report generated: ${result.trades} trades, ₹${Math.round(result.pnl).toLocaleString('en-IN')}` : `Error: ${result.error}`}
        </div>
      )}
    </div>
  )
}


function AutoTuneButton({ onCompleted }) {
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  const runTune = async () => {
    setRunning(true)
    setResult(null)
    try {
      const res = await fetch(`${API}/api/tracking/auto-tune`, { method: 'POST' })
      const data = await res.json()
      const actions = data.actions || []
      const applied = actions.filter(a => a.type === 'auto_tune')
      const flagged = actions.filter(a => a.type === 'auto_tune_flag')
      setResult({
        ok: true,
        status: data.status,
        applied: applied.length,
        flagged: flagged.length,
        details: actions,
      })
      onCompleted()
    } catch (e) {
      setResult({ ok: false, error: e.message })
    }
    setRunning(false)
  }

  return (
    <div>
      <button
        onClick={runTune}
        disabled={running}
        className="w-full py-2 rounded-lg text-sm font-medium bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 disabled:opacity-50 transition-colors"
      >
        {running ? 'Tuning...' : '🔧 Run Auto-Tune'}
      </button>
      {result && (
        <div className="mt-2 space-y-1.5">
          {result.status === 'skipped' ? (
            <p className="text-[10px] text-dark-400 text-center">Need 2+ days of data to auto-tune</p>
          ) : (
            <>
              {result.applied > 0 && (
                <p className="text-[10px] text-emerald-400 text-center">
                  ✅ Auto-applied {result.applied} change(s)
                </p>
              )}
              {result.flagged > 0 && (
                <p className="text-[10px] text-yellow-400 text-center">
                  ⚠️ {result.flagged} suggestion(s) flagged for review
                </p>
              )}
              {result.applied === 0 && result.flagged === 0 && (
                <p className="text-[10px] text-dark-400 text-center">No changes needed</p>
              )}
              {result.details?.map((a, i) => (
                <div key={i} className={`text-[10px] rounded-lg px-2.5 py-1.5 border ${
                  a.type === 'auto_tune' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
                }`}>
                  <span className="font-semibold">{a.parameter}:</span>{' '}
                  {a.type === 'auto_tune'
                    ? `${a.before} → ${a.after}`
                    : a.suggestion || a.reason?.slice(0, 80)
                  }
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}


function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
}
