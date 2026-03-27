import React from 'react'
import {
  LayoutDashboard,
  Briefcase,
  CandlestickChart,
  ScrollText,
  Settings,
  LogOut,
  Info,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Sunrise,
} from 'lucide-react'
import ThemeSwitcher from './ThemeSwitcher'

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', page: 'dashboard' },
  { icon: CandlestickChart, label: 'Equity', page: 'equity' },
  { icon: TrendingUp, label: 'Options', page: 'options' },
  { icon: Sunrise, label: 'BTST', page: 'btst' },
  { icon: TrendingDown, label: 'Futures', page: 'futures', paper: true },
  { icon: Briefcase, label: 'Positions', page: 'positions' },
  { icon: ScrollText, label: 'Trade Log', page: 'logs' },
  { icon: BarChart3, label: 'Daily P&L', page: 'daily-pnl' },
  { icon: Settings, label: 'Settings', page: 'settings' },
  { icon: Info, label: 'About', page: 'about' },
]

export default function Sidebar({ activePage, onNavigate, onLogout }) {
  return (
    <aside
      className="fixed left-0 top-0 h-full w-[72px] bg-gradient-sidebar flex flex-col items-center py-6 z-50 theme-transition"
      style={{ borderRight: '1px solid var(--border)' }}
    >
      {/* Logo */}
      <div className="mb-8">
        <div className="w-10 h-10 rounded-xl bg-gradient-accent flex items-center justify-center text-white font-bold text-lg">
          IT
        </div>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 flex flex-col items-center gap-2">
        {navItems.map((item, i) => (
          <div key={i} className="relative group">
            <button
              onClick={() => onNavigate(item.page)}
              className={`rounded-xl flex items-center justify-center transition-all duration-200 ${
                item.paper ? 'w-9 h-9 opacity-40' : 'w-11 h-11'
              } ${activePage === item.page ? '' : 'hover:opacity-80'}`}
              style={
                activePage === item.page
                  ? { background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)', opacity: 1 }
                  : item.paper
                    ? {}
                    : { color: 'var(--text-secondary)' }
              }
              onMouseEnter={(e) => {
                if (activePage !== item.page) {
                  e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                  if (item.paper) e.currentTarget.style.opacity = '0.7'
                }
              }}
              onMouseLeave={(e) => {
                if (activePage !== item.page) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = item.paper ? '' : 'var(--text-secondary)'
                  if (item.paper) e.currentTarget.style.opacity = '0.4'
                }
              }}
            >
              <item.icon size={item.paper ? 16 : 20} />
            </button>
            <span
              className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-lg"
              style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            >
              {item.label}{item.paper && <span className="ml-1.5 text-[10px] text-yellow-500 font-normal">(Paper)</span>}
            </span>
          </div>
        ))}
      </nav>

      {/* Theme Switcher */}
      <div className="mb-4">
        <ThemeSwitcher compact />
      </div>

      {/* Logout */}
      <div className="relative group">
        <button
          onClick={onLogout}
          className="w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200 hover:text-red-400"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)' }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
        >
          <LogOut size={20} />
        </button>
        <span
          className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-lg"
          style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
        >
          Logout
        </span>
      </div>
    </aside>
  )
}
