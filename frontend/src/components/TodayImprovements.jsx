import React, { useState, useEffect } from 'react'

const API = 'http://localhost:8001'

export default function TodayImprovements() {
  const [changes, setChanges] = useState([])
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/tracking/changelog`)
      .then(r => r.json())
      .then(data => {
        const today = new Date().toISOString().slice(0, 10)
        const todayChanges = (data.changes || []).filter(c =>
          c.date === today && c.type !== 'INITIAL_BASELINE' && c.id
        )
        setChanges(todayChanges)
      })
      .catch(() => {})
  }, [])

  if (dismissed || changes.length === 0) return null

  const autoTuned = changes.filter(c => c.author === 'auto_tuner_v2' || c.type === 'AUTO_TUNE')
  const manual = changes.filter(c => c.author !== 'auto_tuner_v2' && c.type !== 'AUTO_TUNE')

  return (
    <div className="bg-gradient-to-r from-purple-500/10 via-dark-700 to-blue-500/10 rounded-2xl border border-purple-500/20 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🔧</span>
          <h3 className="text-sm font-bold text-purple-400">Today's Improvements Applied</h3>
          <span className="text-[9px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full font-semibold">
            {changes.length} change{changes.length !== 1 ? 's' : ''}
          </span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-gray-500 hover:text-white text-[10px] px-2 py-1 rounded hover:bg-dark-600 transition border border-dark-500"
        >
          Hide
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {changes.slice(0, 6).map((change, i) => (
          <div key={i} className="flex items-start gap-2 bg-dark-600/50 rounded-lg px-3 py-2 border border-dark-500/30">
            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5 ${
              change.type === 'AUTO_TUNE' ? 'bg-purple-500/20 text-purple-400'
                : change.id?.startsWith('P0') ? 'bg-red-500/20 text-red-400'
                : 'bg-blue-500/20 text-blue-400'
            }`}>
              {change.id || change.type}
            </span>
            <div className="min-w-0">
              <p className="text-xs text-white truncate">
                {change.parameter || change.description || change.type}
              </p>
              {change.before !== undefined && change.after !== undefined && (
                <p className="text-[10px] text-gray-400">
                  <span className="text-red-400 line-through">
                    {typeof change.before === 'object' ? JSON.stringify(change.before).slice(0, 30) : String(change.before).slice(0, 20)}
                  </span>
                  {' → '}
                  <span className="text-emerald-400">
                    {typeof change.after === 'object' ? JSON.stringify(change.after).slice(0, 30) : String(change.after).slice(0, 20)}
                  </span>
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {changes.length > 6 && (
        <p className="text-[10px] text-gray-500 mt-2 text-center">
          +{changes.length - 6} more changes — see Tracker sidebar for details
        </p>
      )}

      {autoTuned.length > 0 && (
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-purple-400">
          <span>🧠</span>
          <span>{autoTuned.length} auto-tuned by system (strategy boosts, SL, volume filter)</span>
        </div>
      )}
    </div>
  )
}
