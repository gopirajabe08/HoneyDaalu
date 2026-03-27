import React, { useState, useEffect, useMemo } from 'react'
import { RefreshCw, Briefcase, TrendingUp, TrendingDown, Filter, BarChart3, Package } from 'lucide-react'
import { getPositions, getOrderbook } from '../services/api'

const ORDER_STATUS_MAP = { 1: 'Pending', 2: 'Filled', 4: 'Transit', 5: 'Rejected', 6: 'Cancelled' }

// Charges estimate per closed position (brokerage + STT + exchange + GST + stamp for typical intraday)
const CHARGES_PER_POSITION = 65

// Classify a position into a group based on symbol and product type
function classifyPosition(pos) {
  const symbol = (pos.symbol || '').toUpperCase()
  const productType = (pos.productType || pos.product_type || '').toUpperCase()

  // CNC = delivery / BTST
  if (productType === 'CNC') return 'BTST'
  // Options: symbols containing CE or PE (e.g., NIFTY26MAR25000CE)
  if (/\d+(CE|PE)$/.test(symbol) || symbol.includes('-CE') || symbol.includes('-PE')) return 'OPTIONS'
  // Default: equity
  return 'EQUITY'
}

// Clean display symbol
function displaySymbol(symbol) {
  return (symbol || '').replace('NSE:', '').replace('BSE:', '').replace('MCX:', '').replace('-EQ', '')
}

// Section config for each group
const GROUP_CONFIG = {
  EQUITY: { label: 'Equity', icon: BarChart3, color: 'text-blue-400', bgAccent: 'bg-blue-500/10', borderAccent: 'border-blue-500/30' },
  OPTIONS: { label: 'Options', icon: TrendingUp, color: 'text-violet-400', bgAccent: 'bg-violet-500/10', borderAccent: 'border-violet-500/30' },
  BTST: { label: 'BTST / CNC', icon: Package, color: 'text-emerald-400', bgAccent: 'bg-emerald-500/10', borderAccent: 'border-emerald-500/30' },
}

function PositionSection({ group, positions, allClosed }) {
  const config = GROUP_CONFIG[group] || GROUP_CONFIG.EQUITY
  const Icon = config.icon

  const openPositions = positions.filter(p => (p.netQty || p.qty || 0) !== 0)
  const closedPositions = positions.filter(p => (p.netQty || p.qty || 0) === 0 && ((p.buyQty || 0) > 0 || (p.sellQty || 0) > 0))

  const unrealizedPnl = openPositions.reduce((sum, p) => sum + (p.unrealized_profit ?? p.pl ?? 0), 0)
  const realizedPnl = closedPositions.reduce((sum, p) => sum + (p.realized_profit ?? p.pl ?? 0), 0)
  const totalPnl = unrealizedPnl + realizedPnl
  const chargesEstimate = closedPositions.length * CHARGES_PER_POSITION
  const netPnl = totalPnl - chargesEstimate

  const allPositions = [...openPositions, ...closedPositions]

  if (allPositions.length === 0) return null

  return (
    <div className="mb-4">
      {/* Section Header */}
      <div className={`flex items-center justify-between px-4 py-2.5 rounded-t-xl border ${config.bgAccent} ${config.borderAccent}`}>
        <div className="flex items-center gap-2">
          <Icon size={14} className={config.color} />
          <span className={`text-xs font-semibold ${config.color}`}>{config.label}</span>
          <span className="text-[10px] text-gray-500">
            {openPositions.length} open{closedPositions.length > 0 ? `, ${closedPositions.length} closed` : ''}
          </span>
        </div>
        <div className="flex items-center gap-4">
          {closedPositions.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500">Charges:</span>
              <span className="text-[10px] font-medium text-yellow-400">{'\u20B9'}{chargesEstimate}</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500">P&L:</span>
            <span className={`text-xs font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{totalPnl.toFixed(2)}
            </span>
          </div>
          {chargesEstimate > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500">Net:</span>
              <span className={`text-xs font-bold ${netPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {netPnl >= 0 ? '+' : ''}{'\u20B9'}{netPnl.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Position Table */}
      <div className="rounded-b-xl border border-t-0 overflow-hidden" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
        <table className="w-full">
          <thead>
            <tr style={{ borderBottomWidth: '1px', borderColor: 'var(--border)' }}>
              <th className="text-left text-[10px] font-medium px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>Symbol</th>
              <th className="text-center text-[10px] font-medium px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>Side</th>
              <th className="text-right text-[10px] font-medium px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>Qty</th>
              <th className="text-right text-[10px] font-medium px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>Entry Avg</th>
              <th className="text-right text-[10px] font-medium px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>LTP</th>
              <th className="text-right text-[10px] font-medium px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>P&L</th>
              <th className="text-center text-[10px] font-medium px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>Product</th>
              <th className="text-center text-[10px] font-medium px-4 py-2.5" style={{ color: 'var(--text-secondary)' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {allPositions.map((pos, i) => {
              const qty = pos.netQty || pos.qty || 0
              const isOpen = qty !== 0
              const isBuy = qty > 0 || (qty === 0 && (pos.buyQty || 0) > (pos.sellQty || 0))
              const pnl = isOpen ? (pos.unrealized_profit ?? pos.pl ?? 0) : (pos.realized_profit ?? pos.pl ?? 0)
              const symbol = displaySymbol(pos.symbol)
              const avgPrice = isBuy ? (pos.buyAvg || pos.avgPrice || 0) : (pos.sellAvg || pos.avgPrice || 0)
              const productType = (pos.productType || pos.product_type || '').toUpperCase()

              return (
                <tr key={i} className={`border-b border-dark-600/50 hover:bg-dark-600/30 transition-colors ${!isOpen ? 'opacity-50' : ''}`}>
                  <td className="px-4 py-2.5 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{symbol}</td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded ${isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                      {isBuy ? <><TrendingUp size={10} /> BUY</> : <><TrendingDown size={10} /> SELL</>}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right text-xs" style={{ color: 'var(--text-primary)' }}>{Math.abs(qty) || `${pos.buyQty || 0}/${pos.sellQty || 0}`}</td>
                  <td className="px-3 py-2.5 text-right text-xs" style={{ color: 'var(--text-primary)' }}>{'\u20B9'}{avgPrice.toFixed(2)}</td>
                  <td className="px-3 py-2.5 text-right text-xs" style={{ color: 'var(--text-primary)' }}>{'\u20B9'}{(pos.ltp || 0).toFixed(2)}</td>
                  <td className={`px-3 py-2.5 text-right text-xs font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {pnl >= 0 ? '+' : ''}{'\u20B9'}{pnl.toFixed(2)}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${
                      productType === 'INTRADAY' || productType === 'MARGIN' ? 'bg-orange-500/10 text-orange-400' :
                      productType === 'CNC' ? 'bg-emerald-500/10 text-emerald-400' :
                      productType === 'BO' ? 'bg-blue-500/10 text-blue-400' :
                      'bg-gray-500/10 text-gray-400'
                    }`}>
                      {productType || '-'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {isOpen ? (
                      <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-500/30">
                        OPEN
                      </span>
                    ) : (
                      <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-gray-500/15 text-gray-500 border border-gray-500/30">
                        CLOSED
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

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

  // Group positions by type
  const grouped = useMemo(() => {
    const groups = { EQUITY: [], OPTIONS: [], BTST: [] }
    positions.forEach(p => {
      const group = classifyPosition(p)
      groups[group].push(p)
    })
    return groups
  }, [positions])

  // Positions with any activity (open or traded today)
  const allTraded = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
  const openPositions = positions.filter(p => (p.netQty || p.qty || 0) !== 0)
  const closedPositions = allTraded.filter(p => (p.netQty || p.qty || 0) === 0)

  // Grand totals
  const totalUnrealized = openPositions.reduce((sum, p) => sum + (p.unrealized_profit ?? p.pl ?? 0), 0)
  const totalRealized = closedPositions.reduce((sum, p) => sum + (p.realized_profit ?? p.pl ?? 0), 0)
  const grandTotalPnl = totalUnrealized + totalRealized
  const totalChargesEstimate = closedPositions.length * CHARGES_PER_POSITION
  const grandNetPnl = grandTotalPnl - totalChargesEstimate

  if (!fyersConnected) {
    return (
      <div className="rounded-2xl border p-12 text-center" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
        <Briefcase size={32} className="mx-auto mb-3" style={{ color: 'var(--text-secondary)' }} />
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Connect your Fyers account to view positions</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Briefcase size={18} className="text-orange-400" />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Positions & Orders</h2>
        </div>
        <button onClick={refresh} disabled={loading} className="flex items-center gap-1.5 text-xs hover:text-gray-300 rounded-lg border px-3 py-1.5 transition-colors" style={{ color: 'var(--text-secondary)', backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 rounded-xl p-1 border w-fit" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
        {['positions', 'orders'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all ${
              tab === t ? 'bg-dark-600 text-white' : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            {t === 'positions' ? `Positions (${allTraded.length})` : `Orders (${orders.length})`}
          </button>
        ))}
      </div>

      {/* Positions Tab */}
      {tab === 'positions' && (
        <div>
          {/* Grand Total Summary */}
          {allTraded.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
              <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
                <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Open Positions</p>
                <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{openPositions.length}</p>
              </div>
              <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
                <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Unrealized P&L</p>
                <p className={`text-lg font-bold ${totalUnrealized >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalUnrealized >= 0 ? '+' : ''}{'\u20B9'}{totalUnrealized.toFixed(0)}
                </p>
              </div>
              <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
                <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Realized P&L</p>
                <p className={`text-lg font-bold ${totalRealized >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalRealized >= 0 ? '+' : ''}{'\u20B9'}{totalRealized.toFixed(0)}
                </p>
              </div>
              <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
                <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Charges (est.)</p>
                <p className="text-lg font-bold text-yellow-400">
                  {'\u20B9'}{totalChargesEstimate}
                </p>
              </div>
              <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
                <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>Net P&L</p>
                <p className={`text-lg font-bold ${grandNetPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {grandNetPnl >= 0 ? '+' : ''}{'\u20B9'}{grandNetPnl.toFixed(0)}
                </p>
              </div>
            </div>
          )}

          {/* Grouped Position Sections */}
          {allTraded.length === 0 ? (
            <div className="rounded-2xl border p-12 text-center" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
              <Briefcase size={28} className="mx-auto mb-3" style={{ color: 'var(--text-secondary)' }} />
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No positions today</p>
              <p className="text-[10px] mt-1" style={{ color: 'var(--text-secondary)' }}>Positions will appear once trades are executed via Fyers</p>
            </div>
          ) : (
            <>
              {['EQUITY', 'OPTIONS', 'BTST'].map(group => (
                <PositionSection key={group} group={group} positions={grouped[group]} />
              ))}
            </>
          )}
        </div>
      )}

      {/* Orders Tab */}
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
          <div className="rounded-2xl border overflow-hidden" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)' }}>
            {/* Filter bar */}
            {orders.length > 0 && (
              <div className="flex items-center gap-2 px-5 py-3" style={{ borderBottomWidth: '1px', borderColor: 'var(--border)' }}>
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
              <p className="text-sm text-center py-12" style={{ color: 'var(--text-secondary)' }}>No orders today</p>
            ) : filteredOrders.length === 0 ? (
              <p className="text-sm text-center py-12" style={{ color: 'var(--text-secondary)' }}>No {orderFilter.toLowerCase()} orders</p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottomWidth: '1px', borderColor: 'var(--border)' }}>
                    <th className="text-left text-[10px] font-medium px-5 py-3" style={{ color: 'var(--text-secondary)' }}>Symbol</th>
                    <th className="text-center text-[10px] font-medium px-3 py-3" style={{ color: 'var(--text-secondary)' }}>Side</th>
                    <th className="text-right text-[10px] font-medium px-3 py-3" style={{ color: 'var(--text-secondary)' }}>Qty</th>
                    <th className="text-right text-[10px] font-medium px-3 py-3" style={{ color: 'var(--text-secondary)' }}>Price</th>
                    <th className="text-center text-[10px] font-medium px-3 py-3" style={{ color: 'var(--text-secondary)' }}>Type</th>
                    <th className="text-center text-[10px] font-medium px-5 py-3" style={{ color: 'var(--text-secondary)' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((ord, i) => {
                    const symbol = displaySymbol(ord.symbol)
                    const side = ord.side === 1 ? 'BUY' : 'SELL'
                    const status = ORDER_STATUS_MAP[ord.status] || `S:${ord.status}`
                    const statusColor = status === 'Filled' ? 'text-green-400' : status === 'Pending' ? 'text-yellow-400' : status === 'Transit' ? 'text-blue-400' : 'text-red-400'
                    const typeMap = { 1: 'Limit', 2: 'Market', 3: 'SL', 4: 'SL-M' }
                    return (
                      <tr key={i} className="border-b border-dark-600/50 hover:bg-dark-600/30 transition-colors">
                        <td className="px-5 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{symbol}</td>
                        <td className="px-3 py-3 text-center">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${side === 'BUY' ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                            {side}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-right text-xs" style={{ color: 'var(--text-primary)' }}>{ord.qty}</td>
                        <td className="px-3 py-3 text-right text-xs" style={{ color: 'var(--text-primary)' }}>{'\u20B9'}{(ord.limitPrice || ord.tradedPrice || 0).toFixed(2)}</td>
                        <td className="px-3 py-3 text-center text-[10px]" style={{ color: 'var(--text-secondary)' }}>{typeMap[ord.type] || ord.type}</td>
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
