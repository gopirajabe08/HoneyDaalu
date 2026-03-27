import React from 'react'
import { useTheme } from '../contexts/ThemeContext'

const themes = [
  { id: 'dark', label: 'Dark', color: '#0a0a0f', ring: '#f97316' },
  { id: 'light', label: 'Light', color: '#f8fafc', ring: '#2563eb' },
  { id: 'midnight', label: 'Midnight', color: '#0f172a', ring: '#06b6d4' },
]

export default function ThemeSwitcher({ compact = false }) {
  const { theme, setTheme } = useTheme()

  if (compact) {
    // Compact version for sidebar — 3 small stacked circles
    return (
      <div className="flex flex-col items-center gap-1.5">
        {themes.map((t) => (
          <button
            key={t.id}
            onClick={() => setTheme(t.id)}
            title={t.label}
            className="relative group no-transition"
          >
            <div
              className={`w-5 h-5 rounded-full border-2 transition-all duration-200 ${
                theme === t.id
                  ? 'scale-110 shadow-lg'
                  : 'opacity-50 hover:opacity-80 hover:scale-105'
              }`}
              style={{
                backgroundColor: t.color,
                borderColor: theme === t.id ? t.ring : 'var(--border)',
                boxShadow: theme === t.id ? `0 0 8px ${t.ring}40` : 'none',
              }}
            />
            <span className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2 py-1 rounded-lg text-[10px] font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-lg"
              style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            >
              {t.label}
            </span>
          </button>
        ))}
      </div>
    )
  }

  // Full version with labels (for settings page or header)
  return (
    <div className="flex items-center gap-2">
      {themes.map((t) => (
        <button
          key={t.id}
          onClick={() => setTheme(t.id)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
            theme === t.id
              ? 'ring-2 shadow-md'
              : 'opacity-60 hover:opacity-90'
          }`}
          style={{
            backgroundColor: theme === t.id ? 'var(--bg-tertiary)' : 'transparent',
            color: theme === t.id ? 'var(--accent)' : 'var(--text-secondary)',
            borderColor: 'var(--border)',
            border: '1px solid var(--border)',
            ringColor: theme === t.id ? t.ring : undefined,
            '--tw-ring-color': t.ring,
          }}
        >
          <div
            className="w-3.5 h-3.5 rounded-full border"
            style={{
              backgroundColor: t.color,
              borderColor: t.ring,
            }}
          />
          {t.label}
        </button>
      ))}
    </div>
  )
}
