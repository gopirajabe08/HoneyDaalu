import React, { useState, useEffect } from 'react'
import { Clock, CalendarOff, ChevronDown } from 'lucide-react'
import { getMarketStatus } from '../services/api'

export default function Header({ fyersStatus }) {
  const [marketStatus, setMarketStatus] = useState(null)
  const [time, setTime] = useState('')
  const [showHolidays, setShowHolidays] = useState(false)

  useEffect(() => {
    checkMarket()
    const marketInterval = setInterval(checkMarket, 60000)
    const clockInterval = setInterval(() => {
      setTime(new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }, 1000)
    return () => { clearInterval(marketInterval); clearInterval(clockInterval) }
  }, [])

  async function checkMarket() {
    try { setMarketStatus(await getMarketStatus()) } catch {}
  }

  const profileName = fyersStatus?.profile?.name || 'Trader'
  const profileId = fyersStatus?.profile?.fy_id || ''
  const upcomingHolidays = marketStatus?.upcoming_holidays || []
  const nextTradingDay = marketStatus?.next_trading_day || ''

  return (
    <header className="flex items-center justify-between px-6 py-4">
      {/* Left - Brand */}
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-pink-400">Intra</span>
          <span className="text-white">Trading</span>
        </h1>
        <span className="text-[10px] text-gray-500 bg-dark-700 px-2 py-0.5 rounded-full border border-dark-500">Nifty 500</span>
      </div>

      {/* Center - Market status + Clock + Holidays */}
      <div className="flex items-center gap-4">
        {marketStatus && (
          <div className="relative">
            <button
              onClick={() => setShowHolidays(!showHolidays)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer ${
                marketStatus.is_open
                  ? 'bg-green-500/10 text-green-400'
                  : 'bg-dark-700 text-gray-400 border border-dark-500'
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${marketStatus.is_open ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
              {marketStatus.message}
              {upcomingHolidays.length > 0 && <ChevronDown size={12} className={`transition-transform ${showHolidays ? 'rotate-180' : ''}`} />}
            </button>

            {/* Holidays dropdown */}
            {showHolidays && upcomingHolidays.length > 0 && (
              <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 z-50 bg-dark-700 border border-dark-500 rounded-xl shadow-xl p-3 min-w-[240px]">
                {!marketStatus.is_open && nextTradingDay && (
                  <div className="flex items-center gap-2 text-xs text-green-400 mb-2 pb-2 border-b border-dark-500">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
                    Next trading day: {nextTradingDay}
                  </div>
                )}
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <CalendarOff size={10} /> Upcoming Holidays
                </p>
                {upcomingHolidays.map((h, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 py-1 text-xs">
                    <span className="text-gray-300">{h.name}</span>
                    <span className="text-gray-500 text-[10px] whitespace-nowrap">{h.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-1.5 text-gray-400">
          <Clock size={13} />
          <span className="text-xs tabular-nums font-mono">{time}</span>
          <span className="text-[10px] text-gray-500">IST</span>
        </div>
      </div>

      {/* Right - User */}
      <div className="flex items-center gap-3">
        {fyersStatus?.connected ? (
          <div className="flex items-center gap-2 bg-dark-700 border border-dark-500 rounded-xl px-3 py-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center text-white text-[10px] font-bold">
              {profileName.charAt(0)}
            </div>
            <div>
              <p className="text-xs text-white font-medium leading-tight">{profileName}</p>
              <p className="text-[9px] text-gray-500">{profileId}</p>
            </div>
            <div className="w-2 h-2 rounded-full bg-green-400" />
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-dark-700 border border-dark-500 rounded-xl px-3 py-2">
            <div className="w-7 h-7 rounded-lg bg-dark-600 flex items-center justify-center text-gray-500 text-[10px] font-bold">
              ?
            </div>
            <span className="text-xs text-gray-400">Not connected</span>
          </div>
        )}
      </div>
    </header>
  )
}
