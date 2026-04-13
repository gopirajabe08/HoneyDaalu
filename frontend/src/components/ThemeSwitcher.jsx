import React from 'react'
import { Palette } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

const THEMES = [
  { id: 'cosmos', label: 'Cosmos', icon: '🌌' },
  { id: 'ocean', label: 'Ocean', icon: '🌊' },
  { id: 'forest', label: 'Forest', icon: '🌲' },
  { id: 'sunset', label: 'Sunset', icon: '🌅' },
  { id: 'crystal', label: 'Crystal', icon: '💎' },
]

export default function ThemeSwitcher({ compact = false }) {
  const { theme, setTheme } = useTheme()

  const currentIndex = THEMES.findIndex(t => t.id === theme)
  const current = THEMES[currentIndex] || THEMES[0]
  const next = THEMES[(currentIndex + 1) % THEMES.length]

  function cycleTheme() {
    setTheme(next.id)
  }

  if (compact) {
    return (
      <div className="relative group">
        <button
          onClick={cycleTheme}
          className="w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200 hover:scale-105"
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
          }}
          title={`Theme: ${current.label} → Click for ${next.label}`}
        >
          <span className="text-base">{current.icon}</span>
        </button>
        <span
          className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-lg"
          style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
        >
          {current.label} → {next.label}
        </span>
      </div>
    )
  }

  // Full version for settings
  return (
    <div className="flex items-center gap-2">
      {THEMES.map((t) => (
        <button
          key={t.id}
          onClick={() => setTheme(t.id)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
            theme === t.id ? 'ring-2' : 'opacity-60 hover:opacity-90'
          }`}
          style={{
            backgroundColor: theme === t.id ? 'var(--bg-tertiary)' : 'transparent',
            color: theme === t.id ? 'var(--accent)' : 'var(--text-secondary)',
            border: '1px solid var(--border)',
          }}
        >
          <span>{t.icon}</span>
          {t.label}
        </button>
      ))}
    </div>
  )
}
