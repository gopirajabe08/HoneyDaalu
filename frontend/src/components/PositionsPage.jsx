import React, { useState, useEffect, useMemo } from 'react'
import { RefreshCw, Briefcase, TrendingUp, TrendingDown, Filter } from 'lucide-react'
import { getPositions, getOrderbook } from '../services/api'

const ORDER_STATUS_MAP = { 1: 'Pending', 2: 'Filled', 4: 'Transit', 5: 'Rejected', 6: 'Cancelled' }

export default function PositionsPage({ fyersConnected }) {
  const [tab, setTab] = useState('positions')
  const [positions, setPositions] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(false)
  const [orderFilter, setOrderFilter] = useState('all') // 'all', 'Filled', 'Pending', 'Rejected', 'Cancelled'

  useEffect(() => { if (fyersConnected) refresh() }, [fyersConnected])

  async function refresh() {
    setLoading(true)
    try {
      const [posRes, ordRes] = await Promise.all([getPositions(), getOrderbook()])
      setPositions(posRes?.netPositions || posRes?.data?.netPositions || [])
      setOrders(ordRes?.orderBook || ordRes?.data?.orderBook || [])
    } catch {}
    setLoading(false)
  }

  if (!fyersConnected) {
    return (
      <div className="bg-dark-700 rounded-2xl border border-dark-500 p-12 text-center">
        <Briefcase size={32} className="text-gray-600 mx-auto mb-3" />
        <p className="text-sm text-gray-400">Connect your Fyers account to view positions</p>
      </div>
    )
  }

  const openPositions = positions.filter(p => (p.netQty || p.qty || 0) !== 0)
  const totalPnl = openPositions.reduce((sum, p) => sum + (p.pl || p.unrealized_profit || 0), 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Briefcase size={18} className="text-orange-400" />
          <h2 className="text-lg font-semibold text-white">Positions & Orders</h2>
        </div>
        <button onClick={refresh} disabled={loading} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 bg-dark-700 border border-dark-500 rounded-lg px-3 py-1.5 transition-colors">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-dark-700 rounded-xl p-1 border border-dark-500 w-fit">
        {['positions', 'orders'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all ${
              tab === t ? 'bg-dark-600 text-white' : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            {t === 'positions' ? `Positions (${openPositions.length})` : `Orders (${orders.length})`}
          </button>
        ))}
      </div>

      {/* Positions */}
      {tab === 'positions' && (
        <div className="bg-dark-700 rounded-2xl border border-dark-500 overflow-hidden">
          {openPositions.length > 0 && (
            <div className="flex items-center justify-between px-5 py-3 border-b border-dark-500">
              <span className="text-xs text-gray-400">Total Unrealized P&L</span>
              <span className={`text-sm font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{totalPnl.toFixed(2)}
              </span>
            </div>
          )}
          {openPositions.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-12">No open positions</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-500">
                  <th className="text-left text-[10px] text-gray-400 font-medium px-5 py-3">Symbol</th>
                  <th className="text-center text-[10px] text-gray-400 font-medium px-3 py-3">Side</th>
                  <th className="text-right text-[10px] text-gray-400 font-medium px-3 py-3">Qty</th>
                  <th className="text-right text-[10px] text-gray-400 font-medium px-3 py-3">Avg Price</th>
                  <th className="text-right text-[10px] text-gray-400 font-medium px-3 py-3">LTP</th>
                  <th className="text-right text-[10px] text-gray-400 font-medium px-5 py-3">P&L</th>
                </tr>
              </thead>
              <tbody>
                {openPositions.map((pos, i) => {
                  const qty = pos.netQty || pos.qty || 0
                  const pnl = pos.pl || pos.unrealized_profit || 0
                  const symbol = (pos.symbol || '').replace('NSE:', '').replace('-EQ', '')
                  return (
                    <tr key={i} className="border-b border-dark-600/50 hover:bg-dark-600/30 transition-colors">
                      <td className="px-5 py-3 text-sm font-medium text-white">{symbol}</td>
                      <td className="px-3 py-3 text-center">
                        <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded ${qty > 0 ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                          {qty > 0 ? <><TrendingUp size={10} /> LONG</> : <><TrendingDown size={10} /> SHORT</>}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right text-xs text-gray-300">{Math.abs(qty)}</td>
                      <td className="px-3 py-3 text-right text-xs text-gray-300">{'\u20B9'}{(pos.avgPrice || pos.buyAvg || 0).toFixed(2)}</td>
                      <td className="px-3 py-3 text-right text-xs text-gray-300">{'\u20B9'}{(pos.ltp || 0).toFixed(2)}</td>
                      <td className={`px-5 py-3 text-right text-xs font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pnl >= 0 ? '+' : ''}{'\u20B9'}{pnl.toFixed(2)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Orders */}
      {tab === 'orders' && (() => {
        const statusCounts = {}
        orders.forEach(ord => {
          const s = ORDER_STATUS_MAP[ord.status] || 'Other'
          statusCounts[s] = (statusCounts[s] || 0) + 1
        })
        const filterOptions = ['all', ...Object.keys(statusCounts)]
        const filteredOrders = orderFilter === 'all'
          ? orders
          : orders.filter(ord => (ORDER_STATUS_MAP[ord.status] || 'Other') === orderFilter)

        return (
          <div className="bg-dark-700 rounded-2xl border border-dark-500 overflow-hidden">
            {/* Filter bar */}
            {orders.length > 0 && (
              <div className="flex items-center gap-2 px-5 py-3 border-b border-dark-500">
                <Filter size={12} className="text-gray-500" />
                <span className="text-[10px] text-gray-500 font-medium">Filter:</span>
                <div className="flex gap-1.5">
                  {filterOptions.map(f => {
                    const count = f === 'all' ? orders.length : (statusCounts[f] || 0)
                    const isActive = orderFilter === f
                    const colorMap = {
                      all: isActive ? 'bg-dark-500 text-white border-dark-400' : '',
                      Filled: isActive ? 'bg-green-500/15 text-green-400 border-green-500/30' : '',
                      Pending: isActive ? 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' : '',
                      Rejected: isActive ? 'bg-red-500/15 text-red-400 border-red-500/30' : '',
                      Cancelled: isActive ? 'bg-gray-500/15 text-gray-400 border-gray-500/30' : '',
                      Transit: isActive ? 'bg-blue-500/15 text-blue-400 border-blue-500/30' : '',
                    }
                    return (
                      <button
                        key={f}
                        onClick={() => setOrderFilter(f)}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-all ${
                          isActive
                            ? colorMap[f] || 'bg-dark-500 text-white border-dark-400'
                            : 'bg-dark-800 text-gray-500 border-dark-600 hover:text-gray-300 hover:border-dark-500'
                        }`}
                      >
                        {f === 'all' ? 'All' : f} ({count})
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {orders.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-12">No orders today</p>
            ) : filteredOrders.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-12">No {orderFilter.toLowerCase()} orders</p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-500">
                    <th className="text-left text-[10px] text-gray-400 font-medium px-5 py-3">Symbol</th>
                    <th className="text-center text-[10px] text-gray-400 font-medium px-3 py-3">Side</th>
                    <th className="text-right text-[10px] text-gray-400 font-medium px-3 py-3">Qty</th>
                    <th className="text-right text-[10px] text-gray-400 font-medium px-3 py-3">Price</th>
                    <th className="text-center text-[10px] text-gray-400 font-medium px-3 py-3">Type</th>
                    <th className="text-center text-[10px] text-gray-400 font-medium px-5 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((ord, i) => {
                    const symbol = (ord.symbol || '').replace('NSE:', '').replace('-EQ', '')
                    const side = ord.side === 1 ? 'BUY' : 'SELL'
                    const status = ORDER_STATUS_MAP[ord.status] || `S:${ord.status}`
                    const statusColor = status === 'Filled' ? 'text-green-400' : status === 'Pending' ? 'text-yellow-400' : status === 'Transit' ? 'text-blue-400' : 'text-red-400'
                    const typeMap = { 1: 'Limit', 2: 'Market', 3: 'SL', 4: 'SL-M' }
                    return (
                      <tr key={i} className="border-b border-dark-600/50 hover:bg-dark-600/30 transition-colors">
                        <td className="px-5 py-3 text-sm font-medium text-white">{symbol}</td>
                        <td className="px-3 py-3 text-center">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${side === 'BUY' ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                            {side}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-right text-xs text-gray-300">{ord.qty}</td>
                        <td className="px-3 py-3 text-right text-xs text-gray-300">{'\u20B9'}{(ord.limitPrice || ord.tradedPrice || 0).toFixed(2)}</td>
                        <td className="px-3 py-3 text-center text-[10px] text-gray-400">{typeMap[ord.type] || ord.type}</td>
                        <td className={`px-5 py-3 text-center text-[10px] font-medium ${statusColor}`}>{status}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        )
      })()}
    </div>
  )
}
