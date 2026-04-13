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
  Zap,
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
      className="fixed left-0 top-0 h-full w-[68px] flex flex-col items-center py-5 z-50 theme-transition"
      style={{ backgroundColor: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)' }}
    >
      {/* Logo */}
      <div className="mb-6">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm shadow-lg"
          style={{ background: 'linear-gradient(135deg, var(--gradient-start), var(--gradient-end))', boxShadow: '0 4px 15px var(--accent-glow)' }}
        >
          <Zap size={18} />
        </div>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 flex flex-col items-center gap-1">
        {navItems.map((item, i) => {
          const isActive = activePage === item.page
          return (
            <div key={i} className="relative group">
              <button
                onClick={() => onNavigate(item.page)}
                className={`rounded-xl flex items-center justify-center transition-all duration-200 ${
                  item.paper ? 'w-9 h-9' : 'w-10 h-10'
                }`}
                style={{
                  background: isActive ? 'var(--accent-light)' : 'transparent',
                  color: isActive ? 'var(--accent)' : item.paper ? 'var(--text-muted)' : 'var(--text-secondary)',
                  opacity: item.paper && !isActive ? 0.5 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'
                    e.currentTarget.style.color = 'var(--text-primary)'
                    if (item.paper) e.currentTarget.style.opacity = '0.8'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.color = item.paper ? 'var(--text-muted)' : 'var(--text-secondary)'
                    if (item.paper) e.currentTarget.style.opacity = '0.5'
                  }
                }}
              >
                <item.icon size={item.paper ? 15 : 18} strokeWidth={isActive ? 2.2 : 1.8} />
              </button>

              {/* Tooltip */}
              <span
                className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-xl z-50"
                style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
              >
                {item.label}
                {item.paper && <span className="ml-1.5 text-[9px] font-normal" style={{ color: 'var(--warning)' }}>(Paper)</span>}
              </span>

              {/* Active indicator bar */}
              {isActive && (
                <div
                  className="absolute -left-[1px] top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                  style={{ backgroundColor: 'var(--accent)' }}
                />
              )}
            </div>
          )
        })}
      </nav>

      {/* Theme Switcher */}
      <div className="mb-3">
        <ThemeSwitcher compact />
      </div>

      {/* Logout */}
      <div className="relative group">
        <button
          onClick={onLogout}
          className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--negative-light)'; e.currentTarget.style.color = 'var(--negative)' }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)' }}
        >
          <LogOut size={18} strokeWidth={1.8} />
        </button>
        <span
          className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-xl"
          style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
        >
          Logout
        </span>
      </div>
    </aside>
  )
}
