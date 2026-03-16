import React, { useState } from 'react'
import { TrendingUp, TrendingDown, Target, ShieldAlert, Clock, BarChart3, Zap, Loader2 } from 'lucide-react'
import { placeOrder, placeBracketOrder } from '../services/api'

export default function SignalTable({ scanResult, capital, fyersConnected }) {
  if (!scanResult) return null

  const { signals, stocks_scanned, stocks_eligible, scan_time_seconds, error } = scanResult

  return (
    <div className="mt-6">
      {/* Stats bar */}
      <div className="flex items-center gap-6 mb-4">
        <Stat icon={BarChart3} label="Scanned" value={stocks_scanned} />
        <Stat icon={Target} label="Eligible" value={stocks_eligible} color="text-green-400" />
        <Stat icon={Clock} label="Time" value={`${scan_time_seconds}s`} />
        <Stat icon={ShieldAlert} label="Capital" value={`\u20B9${(capital / 1000).toFixed(0)}K`} />
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 mb-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {signals.length === 0 && !error ? (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-8 text-center">
          <p className="text-gray-400 text-sm">No signals found in current scan.</p>
          <p className="text-gray-500 text-xs mt-1">Try a different timeframe or check during market hours.</p>
        </div>
      ) : signals.length > 0 ? (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-500">
                  <th className="text-left text-[11px] font-medium text-gray-400 px-4 py-3">Symbol</th>
                  <th className="text-center text-[11px] font-medium text-gray-400 px-3 py-3">Signal</th>
                  <th className="text-right text-[11px] font-medium text-gray-400 px-3 py-3">Entry</th>
                  <th className="text-right text-[11px] font-medium text-gray-400 px-3 py-3">Stop Loss</th>
                  <th className="text-right text-[11px] font-medium text-gray-400 px-3 py-3">Target 1</th>
                  <th className="text-right text-[11px] font-medium text-gray-400 px-3 py-3">Target 2</th>
                  <th className="text-center text-[11px] font-medium text-gray-400 px-3 py-3">R:R</th>
                  <th className="text-right text-[11px] font-medium text-gray-400 px-3 py-3">Qty</th>
                  <th className="text-right text-[11px] font-medium text-gray-400 px-3 py-3">Capital</th>
                  {fyersConnected && (
                    <th className="text-center text-[11px] font-medium text-gray-400 px-3 py-3">Trade</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {signals.map((sig, i) => (
                  <SignalRow key={i} sig={sig} fyersConnected={fyersConnected} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function SignalRow({ sig, fyersConnected }) {
  const [orderState, setOrderState] = useState('idle') // idle | loading | success | error
  const [orderMsg, setOrderMsg] = useState('')
  const isBuy = sig.signal_type === 'BUY'

  async function handleMarketOrder() {
    setOrderState('loading')
    try {
      const result = await placeOrder({
        symbol: sig.symbol,
        qty: sig.quantity,
        side: isBuy ? 1 : -1,
        order_type: 2, // Market
        product_type: 'INTRADAY',
      })
      if (result.s === 'ok' || result.id) {
        setOrderState('success')
        setOrderMsg('Order placed')
      } else {
        setOrderState('error')
        setOrderMsg(result.message || result.error || 'Failed')
      }
    } catch (e) {
      setOrderState('error')
      setOrderMsg(e.message)
    }
  }

  async function handleBracketOrder() {
    setOrderState('loading')
    try {
      const result = await placeBracketOrder({
        symbol: sig.symbol,
        qty: sig.quantity,
        side: isBuy ? 1 : -1,
        limit_price: sig.entry_price,
        stop_loss: sig.stop_loss,
        target: sig.target_1,
      })
      if (result.s === 'ok' || result.id) {
        setOrderState('success')
        setOrderMsg('BO placed')
      } else {
        setOrderState('error')
        setOrderMsg(result.message || result.error || 'Failed')
      }
    } catch (e) {
      setOrderState('error')
      setOrderMsg(e.message)
    }
  }

  return (
    <tr className="border-b border-dark-600/50 hover:bg-dark-600/30 transition-colors">
      <td className="px-4 py-3">
        <span className="text-sm font-medium text-white">{sig.symbol}</span>
        <div className="text-[10px] text-gray-500">{sig.timeframe}</div>
      </td>
      <td className="px-3 py-3 text-center">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold
          ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
          {isBuy ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {sig.signal_type}
        </span>
      </td>
      <td className="text-right px-3 py-3 text-sm text-gray-200">{'\u20B9'}{sig.entry_price}</td>
      <td className="text-right px-3 py-3 text-sm text-red-400">{'\u20B9'}{sig.stop_loss}</td>
      <td className="text-right px-3 py-3 text-sm text-green-400">{'\u20B9'}{sig.target_1}</td>
      <td className="text-right px-3 py-3 text-sm text-green-400">
        {sig.target_2 ? `\u20B9${sig.target_2}` : '\u2014'}
      </td>
      <td className="text-center px-3 py-3">
        <span className="text-xs font-medium text-orange-400">{sig.risk_reward_ratio}</span>
      </td>
      <td className="text-right px-3 py-3 text-sm text-gray-200">{sig.quantity}</td>
      <td className="text-right px-3 py-3 text-sm text-gray-300">
        {'\u20B9'}{sig.capital_required?.toLocaleString('en-IN')}
      </td>
      {fyersConnected && (
        <td className="px-3 py-3">
          {orderState === 'idle' && (
            <div className="flex gap-1 justify-center">
              <button
                onClick={handleMarketOrder}
                title="Market Order"
                className="px-2 py-1 rounded-md text-[10px] font-semibold bg-green-500/15 text-green-400 hover:bg-green-500/25 transition-colors"
              >
                MKT
              </button>
              <button
                onClick={handleBracketOrder}
                title="Bracket Order (Entry + SL + Target)"
                className="px-2 py-1 rounded-md text-[10px] font-semibold bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors"
              >
                BO
              </button>
            </div>
          )}
          {orderState === 'loading' && (
            <div className="flex justify-center">
              <Loader2 size={14} className="text-orange-400 animate-spin" />
            </div>
          )}
          {orderState === 'success' && (
            <span className="text-[10px] text-green-400 flex items-center justify-center gap-1">
              <Zap size={10} /> {orderMsg}
            </span>
          )}
          {orderState === 'error' && (
            <span className="text-[10px] text-red-400 text-center block truncate max-w-[80px]" title={orderMsg}>
              {orderMsg}
            </span>
          )}
        </td>
      )}
    </tr>
  )
}

function Stat({ icon: Icon, label, value, color = 'text-white' }) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={14} className="text-gray-500" />
      <span className="text-xs text-gray-400">{label}:</span>
      <span className={`text-xs font-semibold ${color}`}>{value}</span>
    </div>
  )
}
