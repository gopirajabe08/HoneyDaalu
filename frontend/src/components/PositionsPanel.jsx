import React, { useState, useEffect } from 'react'
import { RefreshCw, TrendingUp, TrendingDown, List } from 'lucide-react'
import { getPositions, getOrderbook } from '../services/api'

export default function PositionsPanel({ brokerConnected }) {
  const [tab, setTab] = useState('positions')
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (brokerConnected) refresh()
  }, [brokerConnected])

  async function refresh() {
    setLoading(true)
    try {
      const [posRes, ordRes] = await Promise.all([getPositions(), getOrderbook()])
      if (posRes?.netPositions) setPositions(posRes.netPositions)
      else if (Array.isArray(posRes?.data)) setPositions(posRes.data)
      else setPositions([])

      if (ordRes?.orderBook) setOrders(ordRes.orderBook)
      else if (Array.isArray(ordRes?.data)) setOrders(ordRes.data)
      else setOrders([])
    } catch {
      setPositions([])
      setOrders([])
    } finally {
      setLoading(false)
    }
  }

  if (!brokerConnected) return null

  const totalPnl = positions.reduce((sum, p) => sum + (p.pl || p.unrealized_profit || 0), 0)

  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 overflow-hidden mt-6">
      {/* Tabs */}
      <div className="flex items-center border-b border-dark-500">
        <button
          onClick={() => setTab('positions')}
          className={`flex-1 px-4 py-3 text-xs font-medium transition-colors ${
            tab === 'positions' ? 'text-white border-b-2 border-emerald-500' : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Positions ({positions.length})
        </button>
        <button
          onClick={() => setTab('orders')}
          className={`flex-1 px-4 py-3 text-xs font-medium transition-colors ${
            tab === 'orders' ? 'text-white border-b-2 border-emerald-500' : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Orders ({orders.length})
        </button>
        <button
          onClick={refresh}
          disabled={loading}
          className="px-3 py-3 text-gray-500 hover:text-gray-300 transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Positions tab */}
      {tab === 'positions' && (
        <div className="p-4">
          {positions.length === 0 ? (
            <p className="text-xs text-gray-500 text-center py-4">No open positions</p>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] text-gray-400 uppercase">Total P&L</span>
                <span className={`text-sm font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{totalPnl.toFixed(2)}
                </span>
              </div>
              <div className="space-y-2">
                {positions.map((pos, i) => {
                  const pnl = pos.pl || pos.unrealized_profit || 0
                  const symbol = pos.symbol?.replace('NSE:', '').replace('-EQ', '') || ''
                  const qty = pos.netQty || pos.qty || 0
                  return (
                    <div key={i} className="flex items-center justify-between bg-dark-600 rounded-lg px-3 py-2">
                      <div>
                        <div className="flex items-center gap-2">
                          {qty > 0 ? <TrendingUp size={12} className="text-green-400" /> : <TrendingDown size={12} className="text-red-400" />}
                          <span className="text-xs font-medium text-white">{symbol}</span>
                        </div>
                        <span className="text-[10px] text-gray-400">Qty: {qty} | Avg: {'\u20B9'}{(pos.avgPrice || pos.buyAvg || 0).toFixed(2)}</span>
                      </div>
                      <span className={`text-xs font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pnl >= 0 ? '+' : ''}{'\u20B9'}{pnl.toFixed(2)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* Orders tab */}
      {tab === 'orders' && (
        <div className="p-4">
          {orders.length === 0 ? (
            <p className="text-xs text-gray-500 text-center py-4">No orders today</p>
          ) : (
            <div className="space-y-2">
              {orders.map((ord, i) => {
                const symbol = ord.symbol?.replace('NSE:', '').replace('-EQ', '') || ''
                const side = ord.side === 1 ? 'BUY' : 'SELL'
                const status = ord.status === 2 ? 'Filled' : ord.status === 6 ? 'Cancelled' : ord.status === 1 ? 'Pending' : 'Rejected'
                const statusColor = status === 'Filled' ? 'text-green-400' : status === 'Pending' ? 'text-yellow-400' : 'text-red-400'
                return (
                  <div key={i} className="flex items-center justify-between bg-dark-600 rounded-lg px-3 py-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${side === 'BUY' ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                          {side}
                        </span>
                        <span className="text-xs font-medium text-white">{symbol}</span>
                      </div>
                      <span className="text-[10px] text-gray-400">
                        Qty: {ord.qty} | {'\u20B9'}{(ord.limitPrice || ord.tradedPrice || 0).toFixed(2)}
                      </span>
                    </div>
                    <span className={`text-[10px] font-medium ${statusColor}`}>{status}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
