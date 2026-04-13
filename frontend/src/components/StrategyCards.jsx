import React from 'react'
import { TrendingUp, Clock, BarChart2 } from 'lucide-react'
import { strategies, categoryMap } from '../data/mockData'

function StrategyCard({ strategy, isSelected, onSelect }) {
  const catInfo = categoryMap[strategy.category] || {}

  return (
    <button
      onClick={() => onSelect(strategy.id)}
      className={`relative bg-dark-700 rounded-2xl p-4 border text-left transition-all duration-200 card-hover overflow-hidden
        ${isSelected
          ? 'border-emerald-500/50 glow-emerald'
          : 'border-dark-500 hover:border-dark-400'
        }`}
    >
      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent pointer-events-none" />

      <div className="relative z-10">
        {/* Play number badge */}
        <div className="flex items-center justify-between mb-3">
          <span
            className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md"
            style={{ backgroundColor: strategy.color + '20', color: strategy.color }}
          >
            {strategy.shortName}
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-md bg-dark-600 text-gray-400"
          >
            {strategy.category}
          </span>
        </div>

        {/* Name */}
        <h3 className="text-sm font-semibold text-white mb-1.5 leading-tight">
          {strategy.name}
        </h3>

        {/* Description */}
        <p className="text-xs text-gray-400 mb-3 leading-relaxed line-clamp-2">
          {strategy.description}
        </p>

        {/* Indicators */}
        <div className="flex flex-wrap gap-1 mb-3">
          {strategy.indicators.map((ind, i) => (
            <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-dark-600 text-gray-300 border border-dark-500">
              {ind}
            </span>
          ))}
        </div>

        {/* Timeframes */}
        <div className="flex items-center gap-1.5">
          <Clock size={12} className="text-gray-500" />
          {strategy.timeframes.map((tf) => (
            <span key={tf} className="text-[10px] px-1.5 py-0.5 rounded bg-dark-600 text-gray-400">
              {tf}
            </span>
          ))}
        </div>
      </div>
    </button>
  )
}

export default function StrategyCards({ selectedStrategy, onSelectStrategy }) {
  // Group by category
  const categories = [...new Set(strategies.map(s => s.category))]

  return (
    <div>
      {categories.map((cat) => {
        const catInfo = categoryMap[cat] || {}
        const catStrategies = strategies.filter(s => s.category === cat)
        return (
          <div key={cat} className="mb-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: catInfo.color }} />
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {catInfo.label || cat}
              </h2>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {catStrategies.map((strategy) => (
                <StrategyCard
                  key={strategy.id}
                  strategy={strategy}
                  isSelected={selectedStrategy === strategy.id}
                  onSelect={onSelectStrategy}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
