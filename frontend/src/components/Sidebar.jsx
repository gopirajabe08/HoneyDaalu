import React from 'react'
import {
  LayoutDashboard,
  Briefcase,
  CandlestickChart,
  FlaskConical,
  ScrollText,
  Settings,
  LogOut,
  Info,
  BarChart3,
  Microscope,
  TrendingUp,
  TrendingDown,
  Sunrise,
} from 'lucide-react'

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', page: 'dashboard' },
  { icon: CandlestickChart, label: 'Equity', page: 'equity' },
  { icon: TrendingUp, label: 'Options', page: 'options' },
  { icon: TrendingDown, label: 'Futures', page: 'futures' },
  { icon: Sunrise, label: 'BTST', page: 'btst' },
  { icon: FlaskConical, label: 'Backtest', page: 'backtest' },
  { icon: Briefcase, label: 'Positions', page: 'positions' },
  { icon: ScrollText, label: 'Trade Log', page: 'logs' },
  { icon: BarChart3, label: 'Daily P&L', page: 'daily-pnl' },
  { icon: Microscope, label: 'Algo Specialists', page: 'specialists' },
  { icon: Settings, label: 'Settings', page: 'settings' },
  { icon: Info, label: 'About', page: 'about' },
]

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="fixed left-0 top-0 h-full w-[72px] bg-gradient-sidebar border-r border-dark-600 flex flex-col items-center py-6 z-50">
      {/* Logo */}
      <div className="mb-8">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-pink-500 flex items-center justify-center text-white font-bold text-lg">
          IT
        </div>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 flex flex-col items-center gap-2">
        {navItems.map((item, i) => (
          <div key={i} className="relative group">
            <button
              onClick={() => onNavigate(item.page)}
              className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200
                ${activePage === item.page
                  ? 'bg-gradient-to-br from-orange-500/20 to-pink-500/20 text-orange-400'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-dark-600'
                }`}
            >
              <item.icon size={20} />
            </button>
            <span className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg bg-dark-600 border border-dark-500 text-white text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-lg">
              {item.label}
            </span>
          </div>
        ))}
      </nav>

      {/* Logout */}
      <div className="relative group">
        <button
          className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-500 hover:text-red-400 hover:bg-dark-600 transition-all duration-200"
        >
          <LogOut size={20} />
        </button>
        <span className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg bg-dark-600 border border-dark-500 text-white text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 shadow-lg">
          Logout
        </span>
      </div>
    </aside>
  )
}
