import React, { useState, useEffect, useCallback } from 'react'
import { View, Text, ScrollView, TouchableOpacity, RefreshControl, StyleSheet } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { colors } from '../../src/theme/colors'
import Card from '../../src/components/common/Card'
import Badge from '../../src/components/common/Badge'
import { getDailyPnl, getPositions, getOrderbook, getFyersFunds } from '../../src/services/api'
import { formatINR, formatDate } from '../../src/utils/formatters'
import { STRATEGY_NAMES } from '../../src/utils/constants'

const DAY_PRESETS = [7, 14, 30, 90]

function calcFyersBrokerage(positions, orders) {
  const traded = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
  const totalBuyVal = traded.reduce((s, p) => s + (p.buyVal || 0), 0)
  const totalSellVal = traded.reduce((s, p) => s + (p.sellVal || 0), 0)
  const turnover = totalBuyVal + totalSellVal
  const filledCount = (orders || []).filter(o => o.status === 2).length
  const brokerage = filledCount * 20
  const stt = totalSellVal * 0.00025
  const exchange = turnover * 0.0000297
  const gst = (brokerage + exchange) * 0.18
  const sebi = turnover * 0.000001
  const stamp = totalBuyVal * 0.00003
  return Math.round((brokerage + stt + exchange + gst + sebi + stamp) * 100) / 100
}

export default function DailyPnlScreen() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [days, setDays] = useState(30)
  const [sourceMode, setSourceMode] = useState('live')

  useEffect(() => { refresh() }, [days, sourceMode])

  const refresh = async () => {
    setLoading(true)
    try {
      const promises = [getDailyPnl(days, sourceMode)]
      if (sourceMode === 'live') {
        promises.push(getPositions().catch(() => null))
        promises.push(getOrderbook().catch(() => null))
        promises.push(getFyersFunds().catch(() => null))
      }
      const [result, posRes, ordRes, fundsRes] = await Promise.all(promises)
      let rows = Array.isArray(result) ? result : []

      if (sourceMode === 'live' && posRes) {
        const positions = posRes?.netPositions || posRes?.data?.netPositions || []
        const orders = ordRes?.orderBook || ordRes?.data?.orderBook || []
        const traded = positions.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
        const closed = traded.filter(p => (p.netQty || 0) === 0)
        const fWins = closed.filter(p => (p.realized_profit || 0) > 0)
        const fLosers = closed.filter(p => (p.realized_profit || 0) < 0)
        const fRealizedPnl = closed.reduce((s, p) => s + (p.realized_profit || 0), 0)
        const brokerageToday = calcFyersBrokerage(positions, orders)

        const fundList = fundsRes?.fund_limit || []
        const getFundVal = (id) => { const f = fundList.find(x => x.id === id); return f ? (f.equityAmount || 0) : 0 }
        const fyersStartOfDay = getFundVal(9)
        const fyersAvailBal = getFundVal(10)
        const fyersTotalBal = getFundVal(1)
        const fyersFundTransfer = getFundVal(6)

        const todayStr = new Date().toLocaleDateString('en-CA')
        const todayIdx = rows.findIndex(d => d.date === todayStr)
        const fyersEntry = {
          date: todayStr,
          total_pnl: Math.round(fRealizedPnl * 100) / 100,
          brokerage: brokerageToday,
          net_pnl: Math.round((fRealizedPnl - brokerageToday) * 100) / 100,
          trades: traded.length,
          wins: fWins.length,
          losses: fLosers.length,
          win_rate: (fWins.length + fLosers.length) > 0
            ? Math.round((fWins.length / (fWins.length + fLosers.length)) * 1000) / 10 : 0,
          strategies: todayIdx >= 0 ? rows[todayIdx].strategies : [],
          capital_start: fyersStartOfDay,
          capital_end: fyersAvailBal || fyersTotalBal,
          fund_added: fyersFundTransfer > 0 ? fyersFundTransfer : 0,
          fund_withdrawn: fyersFundTransfer < 0 ? Math.abs(fyersFundTransfer) : 0,
        }
        if (todayIdx >= 0) { rows = [...rows]; rows[todayIdx] = fyersEntry }
        else if (traded.length > 0 || fyersStartOfDay > 0) rows = [...rows, fyersEntry]

        // Cumulative P&L
        let cumulative = 0
        for (const r of rows) { cumulative += r.total_pnl; r.cumulative_pnl = Math.round(cumulative * 100) / 100 }

        // Backfill capital
        if (fyersStartOfDay > 0 && rows.length > 0) {
          const todayRowIdx = rows.findIndex(r => r.date === todayStr)
          if (todayRowIdx >= 0) {
            let nextStart = fyersStartOfDay
            for (let i = todayRowIdx - 1; i >= 0; i--) {
              const row = rows[i]
              row.capital_end = Math.round(nextStart * 100) / 100
              const rowNetPnl = row.net_pnl ?? row.total_pnl
              const rowFundNet = (row.fund_added || 0) - (row.fund_withdrawn || 0)
              row.capital_start = Math.round((row.capital_end - rowNetPnl - rowFundNet) * 100) / 100
              nextStart = row.capital_start
            }
          }
        }
      }

      setData(rows)
    } catch { setData([]) }
    setLoading(false)
  }

  const isLive = sourceMode === 'live'
  const accent = isLive ? colors.orange[400] : colors.blue[400]

  // Summary stats
  const totalPnl = data.reduce((s, d) => s + d.total_pnl, 0)
  const totalBrokerage = data.reduce((s, d) => s + (d.brokerage || 0), 0)
  const totalNet = totalPnl - totalBrokerage
  const greenDays = data.filter(d => d.total_pnl > 0).length
  const redDays = data.filter(d => d.total_pnl < 0).length
  const totalTrades = data.reduce((s, d) => s + d.trades, 0)
  const avgDailyPnl = data.length > 0 ? totalPnl / data.length : 0

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={accent} />}>
        <Text style={styles.title}>Daily P&L</Text>

        {/* Source Toggle */}
        <View style={styles.toggleRow}>
          <TouchableOpacity onPress={() => setSourceMode('live')} style={[styles.toggleBtn, isLive && { backgroundColor: colors.orange[400] + '20', borderColor: colors.orange[400] + '40' }]}>
            <Text style={[styles.toggleText, isLive && { color: colors.orange[400] }]}>Live</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setSourceMode('paper')} style={[styles.toggleBtn, !isLive && { backgroundColor: colors.blue[400] + '20', borderColor: colors.blue[400] + '40' }]}>
            <Text style={[styles.toggleText, !isLive && { color: colors.blue[400] }]}>Paper</Text>
          </TouchableOpacity>
        </View>

        {/* Days Filter */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
          {DAY_PRESETS.map(d => (
            <TouchableOpacity key={d} onPress={() => setDays(d)} style={[styles.dayBtn, days === d && { backgroundColor: accent + '20', borderColor: accent + '40' }]}>
              <Text style={[styles.dayText, days === d && { color: accent }]}>{d}d</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Summary Cards */}
        <View style={styles.summaryGrid}>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Gross P&L</Text>
            <Text style={[styles.summaryValue, { color: totalPnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(totalPnl)}</Text>
          </View>
          {isLive && (
            <View style={styles.summaryCard}>
              <Text style={styles.summaryLabel}>Charges</Text>
              <Text style={[styles.summaryValue, { color: colors.red[400] + 'CC' }]}>-{'\u20B9'}{Math.round(totalBrokerage)}</Text>
            </View>
          )}
          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Net P&L</Text>
            <Text style={[styles.summaryValue, { color: totalNet >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(totalNet)}</Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Green / Red</Text>
            <Text style={styles.summaryValue}>
              <Text style={{ color: colors.green[400] }}>{greenDays}</Text>
              <Text style={{ color: colors.text.dim }}> / </Text>
              <Text style={{ color: colors.red[400] }}>{redDays}</Text>
            </Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Total Trades</Text>
            <Text style={[styles.summaryValue, { color: colors.text.primary }]}>{totalTrades}</Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Avg Daily</Text>
            <Text style={[styles.summaryValue, { color: avgDailyPnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(avgDailyPnl)}</Text>
          </View>
        </View>

        {/* Daily Breakdown */}
        <Card style={{ marginTop: 12 }}>
          <Text style={styles.label}>Daily Breakdown ({data.length} days)</Text>
          {data.length === 0 ? (
            <Text style={styles.emptyText}>No {isLive ? 'live' : 'paper'} trade data yet.</Text>
          ) : (
            [...data].reverse().map((d, i) => {
              const netPnl = d.net_pnl ?? d.total_pnl
              const fundNet = (d.fund_added || 0) - (d.fund_withdrawn || 0)
              const hasCapital = (d.capital_start || 0) > 0
              return (
                <View key={i} style={styles.dayRow}>
                  <View style={styles.dayRowTop}>
                    <Text style={styles.dayDate}>{d.date}</Text>
                    <Text style={[styles.dayPnl, { color: d.total_pnl >= 0 ? colors.green[400] : colors.red[400] }]}>
                      {formatINR(d.total_pnl)}
                    </Text>
                  </View>
                  <View style={styles.dayRowBottom}>
                    {isLive && (d.brokerage || 0) > 0 && (
                      <Text style={styles.dayMeta}>Charges: {'\u20B9'}{Math.round(d.brokerage)}</Text>
                    )}
                    {isLive && (
                      <Text style={[styles.dayMeta, { color: netPnl >= 0 ? colors.green[400] + 'AA' : colors.red[400] + 'AA' }]}>
                        Net: {formatINR(netPnl)}
                      </Text>
                    )}
                    <Text style={styles.dayMeta}>{d.trades} trades</Text>
                    <Text style={styles.dayMeta}>
                      <Text style={{ color: colors.green[400] }}>{d.wins}W</Text>
                      <Text style={{ color: colors.text.dim }}>/</Text>
                      <Text style={{ color: colors.red[400] }}>{d.losses}L</Text>
                    </Text>
                    <Text style={styles.dayMeta}>{d.win_rate}%</Text>
                  </View>
                  {hasCapital && (
                    <View style={styles.dayRowBottom}>
                      <Text style={styles.dayMeta}>Cap: {'\u20B9'}{Math.round(d.capital_start).toLocaleString('en-IN')}</Text>
                      <Text style={styles.dayMeta}>{'\u2192'} {'\u20B9'}{Math.round(d.capital_end).toLocaleString('en-IN')}</Text>
                      {fundNet !== 0 && (
                        <Text style={[styles.dayMeta, { color: fundNet > 0 ? colors.blue[400] : colors.orange[400] }]}>
                          Fund: {fundNet > 0 ? '+' : ''}{'\u20B9'}{Math.round(fundNet).toLocaleString('en-IN')}
                        </Text>
                      )}
                    </View>
                  )}
                  {(d.strategies || []).length > 0 && (
                    <View style={styles.stratRow}>
                      {d.strategies.map(s => (
                        <View key={s} style={styles.stratBadge}>
                          <Text style={styles.stratBadgeText}>{STRATEGY_NAMES[s] || s}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              )
            })
          )}

          {/* Totals Row */}
          {data.length > 0 && (
            <View style={styles.totalsRow}>
              <View style={styles.dayRowTop}>
                <Text style={[styles.dayDate, { fontWeight: '800', color: colors.text.primary }]}>Total ({data.length} days)</Text>
                <Text style={[styles.dayPnl, { color: totalPnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(totalPnl)}</Text>
              </View>
              <View style={styles.dayRowBottom}>
                {isLive && totalBrokerage > 0 && (
                  <Text style={[styles.dayMeta, { fontWeight: '700' }]}>Charges: {'\u20B9'}{Math.round(totalBrokerage)}</Text>
                )}
                <Text style={[styles.dayMeta, { fontWeight: '700', color: totalNet >= 0 ? colors.green[400] : colors.red[400] }]}>
                  Net: {formatINR(totalNet)}
                </Text>
                <Text style={[styles.dayMeta, { fontWeight: '700' }]}>{totalTrades} trades</Text>
              </View>
            </View>
          )}
        </Card>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.dark[900] },
  scroll: { flex: 1, padding: 16 },
  title: { fontSize: 20, fontWeight: '800', color: colors.text.primary, marginBottom: 12 },
  label: { fontSize: 11, fontWeight: '600', color: colors.text.secondary, marginBottom: 8 },
  toggleRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  toggleBtn: { flex: 1, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: colors.dark[500], alignItems: 'center', backgroundColor: colors.dark[800] },
  toggleText: { fontSize: 13, fontWeight: '700', color: colors.text.muted },
  dayBtn: { backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[500], borderRadius: 8, paddingHorizontal: 16, paddingVertical: 6, marginRight: 8 },
  dayText: { fontSize: 12, fontWeight: '600', color: colors.text.muted },
  summaryGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  summaryCard: { width: '31%', backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[600], borderRadius: 12, padding: 10 },
  summaryLabel: { fontSize: 9, fontWeight: '600', color: colors.text.muted, marginBottom: 4 },
  summaryValue: { fontSize: 14, fontWeight: '800' },
  emptyText: { fontSize: 12, color: colors.text.dim, textAlign: 'center', paddingVertical: 20 },
  dayRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.dark[600] },
  dayRowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  dayDate: { fontSize: 13, fontWeight: '600', color: colors.text.secondary },
  dayPnl: { fontSize: 14, fontWeight: '800' },
  dayRowBottom: { flexDirection: 'row', gap: 10, marginTop: 4, flexWrap: 'wrap' },
  dayMeta: { fontSize: 10, color: colors.text.muted },
  stratRow: { flexDirection: 'row', gap: 4, marginTop: 4, flexWrap: 'wrap' },
  stratBadge: { backgroundColor: colors.dark[700], paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  stratBadgeText: { fontSize: 9, color: colors.text.muted },
  totalsRow: { paddingVertical: 12, borderTopWidth: 2, borderTopColor: colors.dark[400], marginTop: 4 },
})
