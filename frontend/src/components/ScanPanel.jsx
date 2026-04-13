import React, { useState, useEffect } from 'react'
import { Play, Loader2, AlertCircle, Clock } from 'lucide-react'
import { strategies } from '../data/mockData'
import { getMarketStatus } from '../services/api'

const INTRADAY_TIMEFRAMES = new Set(['3m', '5m', '15m', '30m', '1h'])

export default function ScanPanel({
  selectedStrategy,
  selectedTimeframe,
  setSelectedTimeframe,
  onScan,
  scanning,
}) {
  const [marketStatus, setMarketStatus] = useState(null)

  useEffect(() => {
    checkMarket()
    const interval = setInterval(checkMarket, 60000) // refresh every minute
    return () => clearInterval(interval)
  }, [])

  async function checkMarket() {
    try {
      setMarketStatus(await getMarketStatus())
    } catch {}
  }

  const strategy = strategies.find(s => s.id === selectedStrategy)
  const isIntraday = INTRADAY_TIMEFRAMES.has(selectedTimeframe)
  const marketClosed = marketStatus && !marketStatus.is_open
  const scanDisabled = scanning || (isIntraday && marketClosed)

  if (!strategy) {
    return (
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
        <div className="flex items-center gap-2 text-gray-400">
          <AlertCircle size={18} />
          <p className="text-sm">Select a strategy to start scanning</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
      {/* Market Status */}
      {marketStatus && (
        <div className={`flex items-center gap-2 mb-3 px-3 py-2 rounded-lg text-xs font-medium ${
          marketStatus.is_open
            ? 'bg-green-500/10 text-green-400'
            : 'bg-yellow-500/10 text-yellow-400'
        }`}>
          <div className={`w-2 h-2 rounded-full ${marketStatus.is_open ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'}`} />
          {marketStatus.message}
        </div>
      )}

      <h3 className="text-sm font-semibold text-white mb-1">{strategy.name}</h3>
      <p className="text-xs text-gray-400 mb-4">{strategy.description}</p>

      {/* Timeframe selector */}
      <div className="mb-4">
        <label className="text-xs text-gray-400 mb-2 block">Timeframe</label>
        <div className="flex gap-2 flex-wrap">
          {strategy.timeframes.map((tf) => {
            const tfIntraday = INTRADAY_TIMEFRAMES.has(tf)
            const tfDisabled = tfIntraday && marketClosed
            return (
              <button
                key={tf}
                onClick={() => !tfDisabled && setSelectedTimeframe(tf)}
                className={`px-4 py-2 rounded-lg text-xs font-medium transition-all
                  ${tfDisabled
                    ? 'bg-dark-600 text-gray-600 border border-dark-500 cursor-not-allowed'
                    : selectedTimeframe === tf
                      ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white'
                      : 'bg-dark-600 text-gray-400 border border-dark-500 hover:text-gray-300'
                  }`}
                title={tfDisabled ? 'Available during market hours only' : ''}
              >
                {tf}
                {tfDisabled && <span className="ml-1 text-[8px]">&#128274;</span>}
              </button>
            )
          })}
        </div>
      </div>

      {/* Scan button */}
      <button
        onClick={onScan}
        disabled={scanDisabled}
        className="w-full bg-gradient-to-r from-emerald-500 to-cyan-500 text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {scanning ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Scanning Nifty 500...
          </>
        ) : scanDisabled ? (
          <>
            <Clock size={16} />
            Market Closed
          </>
        ) : (
          <>
            <Play size={16} />
            Scan Nifty 500
          </>
        )}
      </button>

      {isIntraday && marketClosed && (
        <p className="text-[10px] text-yellow-400/70 mt-2 text-center">
          Intraday scans available during market hours (9:15 AM – 3:30 PM IST)
        </p>
      )}

      {/* Strategy details */}
      <div className="mt-4 space-y-2">
        <Detail label="Entry" value={strategy.id.includes('1') ? 'EMA 9 crosses above EMA 21' :
          strategy.id.includes('2') ? 'Pullback to 20 EMA / 50 SMA' :
          strategy.id.includes('3') ? 'Break of trigger candle near VWAP' :
          strategy.id.includes('4') ? 'Break of signal candle in Power Zone' :
          strategy.id.includes('5') ? 'Price above breakout candle high' :
          'Buy above reversal candle high'} />
        <Detail label="Indicators" value={strategy.indicators.join(', ')} />
      </div>
    </div>
  )
}

function Detail({ label, value }) {
  return (
    <div className="flex gap-2">
      <span className="text-[10px] font-medium text-gray-500 uppercase w-16 flex-shrink-0">{label}</span>
      <span className="text-[10px] text-gray-300">{value}</span>
    </div>
  )
}
