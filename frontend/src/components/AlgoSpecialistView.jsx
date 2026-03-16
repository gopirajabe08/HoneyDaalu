import React, { useState, useCallback } from 'react'
import {
  Microscope, TrendingUp, BarChart2, CheckCircle,
  RefreshCw, Rocket, AlertCircle, AlertTriangle,
  Zap, ArrowRight, Target, Sun, ChevronDown, ChevronUp,
  Star, Shield,
} from 'lucide-react'
import { runSpecialistAnalysis, deployRecommendation } from '../services/api'
import { formatINRCompact } from '../utils/formatters'

const today = () =>
  new Date().toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })

/* ── Reusable primitives ──────────────────────────────────── */

const Card = ({ children, className = '' }) => (
  <div className={`bg-dark-800 border border-dark-600 rounded-xl p-5 ${className}`}>
    {children}
  </div>
)

const Badge = ({ label, color }) => {
  const map = {
    green:  'bg-green-900/60 text-green-300 border-green-700',
    red:    'bg-red-900/60 text-red-300 border-red-700',
    yellow: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
    blue:   'bg-blue-900/60 text-blue-300 border-blue-700',
    orange: 'bg-orange-900/60 text-orange-300 border-orange-700',
    purple: 'bg-purple-900/60 text-purple-300 border-purple-700',
    gray:   'bg-dark-600 text-gray-400 border-dark-500',
  }
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border font-semibold ${map[color] ?? map.gray}`}>
      {label}
    </span>
  )
}

/* ── Collapsible section wrapper ─────────────────────────── */

function CollapsibleSection({ icon: Icon, title, color, count, children, defaultOpen = false, borderClass = '' }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card className={borderClass}>
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <Icon size={16} className={color} />
          <h3 className="text-white font-semibold text-sm tracking-wide">{title}</h3>
          {count != null && (
            <span className="text-[10px] text-gray-500 bg-dark-700 px-1.5 py-0.5 rounded">{count}</span>
          )}
        </div>
        {open ? <ChevronUp size={15} className="text-gray-500" /> : <ChevronDown size={15} className="text-gray-500" />}
      </button>
      <div className={`overflow-hidden transition-all duration-300 ease-in-out ${open ? 'max-h-[5000px] opacity-100 mt-4' : 'max-h-0 opacity-0'}`}>
        {children}
      </div>
    </Card>
  )
}

const SPECIALIST_IDS = ['strategist', 'engineer', 'data_scientist', 'risk_manager', 'qa_expert', 'performance_analyst']

/* ── Collect & deduplicate across all specialists ────────── */

function collectInsights(analyses) {
  const highlights = []
  const issues = []
  const tweaks = []
  const nextDay = []
  const recs = []
  const metrics = {}
  const seenKeys = new Set()

  for (const [, analysis] of Object.entries(analyses)) {
    if (!analysis || analysis.error) continue
    if (analysis.metrics) Object.assign(metrics, analysis.metrics)

    for (const h of (analysis.highlights ?? [])) {
      if (!highlights.some(x => x === h)) highlights.push(h)
    }
    for (const l of (analysis.lowlights ?? [])) {
      if (!issues.some(x => x === l)) issues.push(l)
    }
    for (const imp of (analysis.improvements ?? [])) {
      const lower = imp.toLowerCase()
      if (lower.includes('next session') || lower.includes('tomorrow') || lower.includes('continuation') || lower.includes('prioritize') || lower.includes('diversify')) {
        if (!nextDay.some(x => x === imp)) nextDay.push(imp)
      } else {
        if (!tweaks.some(x => x === imp)) tweaks.push(imp)
      }
    }
    for (const rec of (analysis.recommendations ?? [])) {
      const key = rec.deploy_key || `${recs.length}`
      if (!seenKeys.has(key)) {
        seenKeys.add(key)
        recs.push(rec)
      }
    }
  }

  const priorityOrder = { high: 0, medium: 1, low: 2 }
  recs.sort((a, b) => (priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2))

  return { highlights, issues, tweaks, nextDay, recs, metrics }
}

/* ── Build prioritised action plan from all insights ─────── */

function buildActionPlan(insights, deployedKeys) {
  const actions = []

  // 1. Deployable recommendations (highest priority — one-click fixes)
  for (const rec of insights.recs) {
    if (rec.deployable && rec.deploy_key && !deployedKeys.has(rec.deploy_key)) {
      actions.push({
        text: rec.action ?? rec.text ?? rec.message,
        priority: rec.priority || 'medium',
        type: 'deploy',
        deployKey: rec.deploy_key,
      })
    }
  }

  // 2. Strategy tweaks that are actionable
  for (const t of insights.tweaks) {
    const lower = t.toLowerCase()
    // Skip vague ones, keep actionable
    if (lower.includes('pause') || lower.includes('disable') || lower.includes('reduce') ||
        lower.includes('increase') || lower.includes('switch') || lower.includes('tighten') ||
        lower.includes('add') || lower.includes('remove') || lower.includes('investigate')) {
      actions.push({ text: t, priority: 'medium', type: 'tweak' })
    }
  }

  // 3. Next day regime-based advice
  for (const nd of insights.nextDay) {
    actions.push({ text: nd, priority: 'low', type: 'plan' })
  }

  // 4. Critical issues that need attention
  for (const issue of insights.issues) {
    const lower = issue.toLowerCase()
    if (lower.includes('error') || lower.includes('reject') || lower.includes('crash') || lower.includes('fail')) {
      actions.push({ text: issue, priority: 'high', type: 'fix' })
    }
  }

  // Sort: high → medium → low, deploy first within same priority
  const pOrder = { high: 0, medium: 1, low: 2 }
  const tOrder = { fix: 0, deploy: 1, tweak: 2, plan: 3 }
  actions.sort((a, b) => {
    const pd = (pOrder[a.priority] ?? 2) - (pOrder[b.priority] ?? 2)
    if (pd !== 0) return pd
    return (tOrder[a.type] ?? 3) - (tOrder[b.type] ?? 3)
  })

  // Deduplicate
  const seen = new Set()
  return actions.filter(a => {
    if (seen.has(a.text)) return false
    seen.add(a.text)
    return true
  })
}

/* ── Main component ─────────────────────────────────────────── */

export default function AlgoSpecialistView() {
  const [analyses, setAnalyses]           = useState({})
  const [deploying, setDeploying]         = useState({})
  const [deployResults, setDeployResults] = useState({})
  const [generating, setGenerating]       = useState(false)
  const [progress, setProgress]           = useState(0)
  const [deployedToday, setDeployedToday] = useState(() => {
    try {
      const key = `intratrading_deployed_${new Date().toLocaleDateString('en-CA')}`
      return JSON.parse(localStorage.getItem(key) || '[]')
    } catch { return [] }
  })

  const hasAnalysis = Object.keys(analyses).length > 0

  /* Generate — run all 6 specialists, show progress */
  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    setAnalyses({})
    setDeployResults({})
    setProgress(0)

    let done = 0
    await Promise.allSettled(
      SPECIALIST_IDS.map(async (id) => {
        try {
          const result = await runSpecialistAnalysis(id)
          setAnalyses(prev => ({ ...prev, [id]: result }))
        } catch (e) {
          setAnalyses(prev => ({ ...prev, [id]: { error: e.message } }))
        } finally {
          done++
          setProgress(Math.round((done / SPECIALIST_IDS.length) * 100))
        }
      }),
    )
    setGenerating(false)
  }, [])

  /* Deploy a recommendation */
  const handleDeploy = useCallback(async (deployKey, actionText) => {
    setDeploying(prev => ({ ...prev, [deployKey]: true }))
    try {
      const result = await deployRecommendation(deployKey)
      setDeployResults(prev => ({ ...prev, [deployKey]: { success: true, ...result } }))
      const entry = { deploy_key: deployKey, action: actionText, change: result.change, deployed_at: new Date().toISOString() }
      setDeployedToday(prev => {
        const updated = [...prev, entry]
        try {
          const key = `intratrading_deployed_${new Date().toLocaleDateString('en-CA')}`
          localStorage.setItem(key, JSON.stringify(updated))
        } catch {}
        return updated
      })
    } catch (e) {
      setDeployResults(prev => ({ ...prev, [deployKey]: { error: e.message } }))
    }
    setDeploying(prev => ({ ...prev, [deployKey]: false }))
  }, [])

  const insights = hasAnalysis ? collectInsights(analyses) : null
  const deployedKeys = new Set(deployedToday.map(d => d.deploy_key))
  const actionPlan = insights ? buildActionPlan(insights, deployedKeys) : []

  return (
    <div className="space-y-4">
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeSlideIn { animation: fadeSlideIn 0.4s ease-out; }
      `}</style>

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Microscope size={20} className="text-orange-400" />
            Day Review
          </h2>
          <p className="text-gray-500 text-xs mt-0.5">{today()} &middot; Intraday Live</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-orange-500 to-pink-500 hover:from-orange-400 hover:to-pink-400 text-white rounded-lg text-sm font-semibold transition disabled:opacity-40"
        >
          {generating ? (
            <><RefreshCw size={14} className="animate-spin" /> Analysing... {progress}%</>
          ) : hasAnalysis ? (
            <><RefreshCw size={14} /> Re-analyse</>
          ) : (
            <><Zap size={14} /> Analyse Today</>
          )}
        </button>
      </div>

      {/* ── Empty state ──────────────────────────────────────── */}
      {!hasAnalysis && !generating && deployedToday.length === 0 && (
        <Card className="text-center py-12">
          <Microscope size={40} className="text-orange-400 mx-auto mb-4" />
          <p className="text-white font-semibold mb-1">End-of-day review</p>
          <p className="text-gray-500 text-xs max-w-md mx-auto">
            Click "Analyse Today" after market close to get session review, strategy tweaks, and a prioritised action plan.
          </p>
        </Card>
      )}

      {/* ── Generating progress ──────────────────────────────── */}
      {generating && !hasAnalysis && (
        <Card>
          <div className="flex items-center gap-3">
            <RefreshCw size={16} className="animate-spin text-orange-400" />
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-400 text-xs">Analysing today's live trades...</span>
                <span className="text-orange-400 text-xs font-semibold">{progress}%</span>
              </div>
              <div className="w-full h-1.5 bg-dark-600 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-orange-500 to-pink-500 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }} />
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Results ──────────────────────────────────────────── */}
      {insights && (
        <div className="space-y-4 opacity-0 animate-fadeSlideIn" style={{ animationFillMode: 'forwards' }}>

          {/* ── 1. Session Summary (collapsible) ──────────── */}
          <CollapsibleSection
            icon={BarChart2} title="Session Summary" color="text-blue-400"
            count={`${insights.metrics.total_trades ?? insights.metrics.live_trades ?? '?'} trades`}
            defaultOpen={true} borderClass="border-dark-500"
          >
            {Object.keys(insights.metrics).length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                {Object.entries(insights.metrics).map(([key, val]) => {
                  const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                  const isPnl = key.toLowerCase().includes('pnl') || key.toLowerCase().includes('pl')
                  const isRate = key.toLowerCase().includes('rate') || key.toLowerCase().includes('pct')
                  let display = String(val)
                  let color = 'text-white'
                  if (typeof val === 'number') {
                    if (isPnl) {
                      display = `${val >= 0 ? '+' : '-'}${formatINRCompact(val)}`
                      color = val >= 0 ? 'text-green-400' : 'text-red-400'
                    } else if (isRate) {
                      display = `${val}%`
                    } else {
                      display = val.toLocaleString('en-IN')
                    }
                  }
                  return (
                    <div key={key} className="p-2.5 bg-dark-700 rounded-lg">
                      <span className="text-gray-500 text-[10px] block">{label}</span>
                      <span className={`text-sm font-bold ${color}`}>{display}</span>
                    </div>
                  )
                })}
              </div>
            )}
            {insights.highlights.length > 0 && (
              <div className="space-y-1.5">
                {insights.highlights.map((h, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 bg-green-900/10 border border-green-800/20 rounded-lg">
                    <CheckCircle size={13} className="text-green-400 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-300 text-xs leading-relaxed">{h}</span>
                  </div>
                ))}
              </div>
            )}
          </CollapsibleSection>

          {/* ── 2. Issues & Strategy Tweaks (collapsible) ──── */}
          {(insights.issues.length > 0 || insights.tweaks.length > 0) && (
            <CollapsibleSection
              icon={AlertTriangle} title="Issues & Strategy Tweaks" color="text-red-400"
              count={insights.issues.length + insights.tweaks.length}
              defaultOpen={false} borderClass="border-red-500/15"
            >
              {insights.issues.length > 0 && (
                <div className="space-y-1.5 mb-3">
                  {insights.issues.map((l, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-red-900/10 border border-red-800/20 rounded-lg">
                      <AlertCircle size={13} className="text-red-400 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-300 text-xs leading-relaxed">{l}</span>
                    </div>
                  ))}
                </div>
              )}
              {insights.tweaks.length > 0 && (
                <div className="space-y-1.5">
                  {insights.tweaks.map((t, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-orange-900/10 border border-orange-800/20 rounded-lg">
                      <Target size={13} className="text-orange-400 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-300 text-xs leading-relaxed">{t}</span>
                    </div>
                  ))}
                </div>
              )}
            </CollapsibleSection>
          )}

          {/* ── 3. Next Day Outlook (collapsible) ──────────── */}
          {insights.nextDay.length > 0 && (
            <CollapsibleSection
              icon={Sun} title="Next Day Outlook" color="text-yellow-400"
              count={insights.nextDay.length}
              defaultOpen={false} borderClass="border-yellow-500/15"
            >
              <div className="space-y-1.5">
                {insights.nextDay.map((nd, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 bg-blue-900/10 border border-blue-800/20 rounded-lg">
                    <ArrowRight size={13} className="text-blue-400 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-300 text-xs leading-relaxed">{nd}</span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* ── 4. PRIORITY ACTION PLAN (always visible) ───── */}
          {actionPlan.length > 0 && (
            <Card className="border-orange-500/30 bg-gradient-to-b from-dark-800 to-dark-800/80">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1.5 rounded-lg bg-orange-500/15">
                  <Star size={16} className="text-orange-400" />
                </div>
                <div>
                  <h3 className="text-white font-bold text-sm">Priority Action Plan</h3>
                  <p className="text-gray-500 text-[10px]">Ranked actions to improve next session's success</p>
                </div>
              </div>

              <div className="space-y-2">
                {actionPlan.map((action, i) => {
                  const pColor = action.priority === 'high' ? 'red' : action.priority === 'medium' ? 'yellow' : 'blue'
                  const typeIcon = action.type === 'fix' ? AlertCircle
                    : action.type === 'deploy' ? Rocket
                    : action.type === 'tweak' ? Target
                    : ArrowRight
                  const typeColor = action.type === 'fix' ? 'text-red-400'
                    : action.type === 'deploy' ? 'text-green-400'
                    : action.type === 'tweak' ? 'text-orange-400'
                    : 'text-blue-400'
                  const TypeIcon = typeIcon

                  const isDeployable = action.type === 'deploy' && action.deployKey
                  const isDepl = deploying[action.deployKey]
                  const result = deployResults[action.deployKey]
                  const wasDeployed = deployedKeys.has(action.deployKey)

                  return (
                    <div key={i} className="flex items-start gap-3 p-3 bg-dark-700/80 rounded-lg border border-dark-600 hover:border-dark-500 transition">
                      {/* Number */}
                      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-dark-600 flex items-center justify-center">
                        <span className="text-[11px] font-bold text-gray-400">{i + 1}</span>
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge label={action.priority.toUpperCase()} color={pColor} />
                          <TypeIcon size={12} className={typeColor} />
                          <span className="text-[10px] text-gray-500 capitalize">{action.type}</span>
                        </div>
                        <p className="text-gray-200 text-xs leading-relaxed">{action.text}</p>
                      </div>

                      {/* Deploy button for deployable actions */}
                      {isDeployable && !wasDeployed && (
                        <div className="flex-shrink-0 mt-1">
                          {result?.error ? (
                            <span className="flex items-center gap-1 text-red-400 text-[10px]">
                              <AlertCircle size={11} /> Failed
                            </span>
                          ) : (
                            <button
                              onClick={() => handleDeploy(action.deployKey, action.text)}
                              disabled={isDepl}
                              className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white rounded-lg text-[11px] font-semibold transition disabled:opacity-40 whitespace-nowrap"
                            >
                              {isDepl ? (
                                <><RefreshCw size={11} className="animate-spin" /> ...</>
                              ) : (
                                <><Rocket size={11} /> Deploy</>
                              )}
                            </button>
                          )}
                        </div>
                      )}
                      {isDeployable && wasDeployed && (
                        <div className="flex-shrink-0 mt-1">
                          <span className="flex items-center gap-1 text-green-400 text-[10px] font-semibold">
                            <CheckCircle size={11} /> Applied
                          </span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </Card>
          )}

          {/* ── Deployed Today log ─────────────────────────── */}
          {deployedToday.length > 0 && (
            <CollapsibleSection
              icon={CheckCircle} title="Changes Applied Today" color="text-green-400"
              count={deployedToday.length}
              defaultOpen={false} borderClass="border-green-500/20"
            >
              <div className="space-y-1.5">
                {deployedToday.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 bg-green-900/10 border border-green-800/30 rounded-lg">
                    <CheckCircle size={13} className="text-green-400 flex-shrink-0" />
                    <span className="text-green-300 text-xs flex-1">{d.change || d.action}</span>
                    <span className="text-gray-600 text-[10px] flex-shrink-0">
                      {new Date(d.deployed_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}
        </div>
      )}
    </div>
  )
}
