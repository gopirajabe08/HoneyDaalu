import React, { useState, useEffect } from 'react'
import { View, Text, ScrollView, TouchableOpacity, RefreshControl, StyleSheet } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { colors } from '../../src/theme/colors'
import Card from '../../src/components/common/Card'
import Badge from '../../src/components/common/Badge'
import TabBar from '../../src/components/common/TabBar'
import {
  getTradeHistory, getAutoStatus, getPaperStatus,
  getSwingStatus, getSwingPaperStatus,
  getOptionsAutoStatus, getOptionsPaperStatus,
  getOptionsSwingStatus, getOptionsSwingPaperStatus,
} from '../../src/services/api'
import { formatINR, formatTime } from '../../src/utils/formatters'
import { STRATEGY_NAMES, SOURCE_LABELS, SOURCE_COLORS, LOG_COLORS } from '../../src/utils/constants'

const TABS = [
  { id: 'trades', label: 'Trade History', activeColor: colors.orange[400] },
  { id: 'logs', label: 'Engine Logs', activeColor: colors.violet[400] },
]

const DAY_PRESETS = [7, 14, 30, 90]

const SOURCE_FILTERS = [
  { id: 'ALL', label: 'All' },
  { id: 'auto', label: 'EQ Live' },
  { id: 'paper', label: 'EQ Paper' },
  { id: 'swing', label: 'Swing' },
  { id: 'swing_paper', label: 'Sw Paper' },
  { id: 'options_auto', label: 'Opt Live' },
  { id: 'options_paper', label: 'Opt Paper' },
  { id: 'options_swing', label: 'Opt Swing' },
  { id: 'options_swing_paper', label: 'Opt Sw P' },
]

const LOG_FILTERS = ['ALL', 'ORDER', 'SCAN', 'ALERT', 'ERROR']

const EXIT_REASON_COLORS = {
  TARGET_HIT: colors.green[400],
  SL_HIT: colors.red[400],
  SQUARE_OFF: colors.purple[400],
}

export default function TradeLogScreen() {
  const [tab, setTab] = useState('trades')
  const [trades, setTrades] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [days, setDays] = useState(7)
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [logFilter, setLogFilter] = useState('ALL')

  useEffect(() => { refresh() }, [days])

  const refresh = async () => {
    setLoading(true)
    try {
      const emptyLogs = { logs: [] }
      const [history, autoData, paperData, swingData, swingPaperData,
        optAutoData, optPaperData, optSwingData, optSwingPaperData] = await Promise.all([
        getTradeHistory(days).catch(() => []),
        getAutoStatus().catch(() => emptyLogs),
        getPaperStatus().catch(() => emptyLogs),
        getSwingStatus().catch(() => emptyLogs),
        getSwingPaperStatus().catch(() => emptyLogs),
        getOptionsAutoStatus().catch(() => emptyLogs),
        getOptionsPaperStatus().catch(() => emptyLogs),
        getOptionsSwingStatus().catch(() => emptyLogs),
        getOptionsSwingPaperStatus().catch(() => emptyLogs),
      ])
      setTrades(Array.isArray(history) ? history : [])

      const tagLogs = (data, source) => (data.logs || []).map(l => ({ ...l, source }))
      const combined = [
        ...tagLogs(autoData, 'auto'), ...tagLogs(paperData, 'paper'),
        ...tagLogs(swingData, 'swing'), ...tagLogs(swingPaperData, 'swing_paper'),
        ...tagLogs(optAutoData, 'options_auto'), ...tagLogs(optPaperData, 'options_paper'),
        ...tagLogs(optSwingData, 'options_swing'), ...tagLogs(optSwingPaperData, 'options_swing_paper'),
      ].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
      setLogs(combined)
    } catch {}
    setLoading(false)
  }

  // Filter trades
  const filteredTrades = trades.filter(t => {
    if (sourceFilter !== 'ALL' && (t.source || '') !== sourceFilter) return false
    return true
  }).sort((a, b) => (b.closed_at || b.placed_at || '').localeCompare(a.closed_at || a.placed_at || ''))

  // Stats
  const totalPnl = filteredTrades.reduce((s, t) => s + (t.pnl || 0), 0)
  const totalCharges = filteredTrades.reduce((s, t) => s + (t.charges || 0), 0)
  const totalNetPnl = totalPnl - totalCharges
  const wins = filteredTrades.filter(t => (t.pnl || 0) > 0).length
  const losses = filteredTrades.filter(t => (t.pnl || 0) < 0).length
  const winRate = filteredTrades.length > 0 ? ((wins / filteredTrades.length) * 100).toFixed(1) : '0.0'

  // Filter logs
  const filteredLogs = logFilter === 'ALL' ? logs : logs.filter(l => l.level === logFilter)

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.orange[400]} />}>
        <Text style={styles.title}>Trades</Text>

        <TabBar tabs={TABS} active={tab} onSelect={setTab} />

        {tab === 'trades' && (
          <>
            {/* Summary Cards */}
            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>Gross P&L</Text>
                <Text style={[styles.statValue, { color: totalPnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(totalPnl)}</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>Net P&L</Text>
                <Text style={[styles.statValue, { color: totalNetPnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(totalNetPnl)}</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>Win Rate</Text>
                <Text style={[styles.statValue, { color: colors.text.primary }]}>{winRate}%</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>W / L</Text>
                <Text style={styles.statValue}>
                  <Text style={{ color: colors.green[400] }}>{wins}</Text>
                  <Text style={{ color: colors.text.dim }}> / </Text>
                  <Text style={{ color: colors.red[400] }}>{losses}</Text>
                </Text>
              </View>
            </View>

            {/* Days Filter */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 12 }}>
              {DAY_PRESETS.map(d => (
                <TouchableOpacity key={d} onPress={() => setDays(d)} style={[styles.filterBtn, days === d && { backgroundColor: colors.orange[400] + '20', borderColor: colors.orange[400] + '40' }]}>
                  <Text style={[styles.filterText, days === d && { color: colors.orange[400] }]}>{d}d</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Source Filter */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {SOURCE_FILTERS.map(s => (
                <TouchableOpacity key={s.id} onPress={() => setSourceFilter(s.id)} style={[styles.filterBtn, sourceFilter === s.id && { backgroundColor: colors.orange[400] + '20', borderColor: colors.orange[400] + '40' }]}>
                  <Text style={[styles.filterText, sourceFilter === s.id && { color: colors.orange[400] }]}>{s.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Trade List */}
            <Card style={{ marginTop: 12 }}>
              <Text style={styles.label}>Trades ({filteredTrades.length})</Text>
              {filteredTrades.length === 0 ? (
                <Text style={styles.emptyText}>No trades in the last {days} days.</Text>
              ) : (
                filteredTrades.map((t, i) => {
                  const pnl = t.pnl || 0
                  const date = (t.closed_at || t.placed_at || '').split('T')[0]
                  const time = (t.closed_at || t.placed_at || '').split('T')[1]?.substring(0, 8) || ''
                  const exitReason = t.exit_reason || ''
                  const exitColor = EXIT_REASON_COLORS[exitReason] || colors.text.muted
                  const sourceColor = SOURCE_COLORS[t.source] || colors.blue[400]

                  return (
                    <View key={i} style={styles.tradeRow}>
                      <View style={styles.tradeTop}>
                        <View style={{ flex: 1 }}>
                          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                            <Text style={styles.tradeSymbol}>{t.symbol}</Text>
                            <View style={[styles.signalBadge, { backgroundColor: (t.signal_type === 'BUY' ? colors.green[400] : colors.red[400]) + '20' }]}>
                              <Text style={[styles.signalText, { color: t.signal_type === 'BUY' ? colors.green[400] : colors.red[400] }]}>{t.signal_type}</Text>
                            </View>
                          </View>
                          <View style={{ flexDirection: 'row', gap: 6, marginTop: 3 }}>
                            <Text style={styles.tradeMeta}>{date} {time}</Text>
                            <View style={[styles.sourceBadge, { backgroundColor: sourceColor + '15' }]}>
                              <Text style={[styles.sourceText, { color: sourceColor }]}>{SOURCE_LABELS[t.source] || t.source}</Text>
                            </View>
                            {t.strategy && (
                              <Text style={[styles.tradeMeta, { color: colors.text.secondary }]}>{STRATEGY_NAMES[t.strategy] || t.strategy}</Text>
                            )}
                          </View>
                        </View>
                        <View style={{ alignItems: 'flex-end' }}>
                          <Text style={[styles.tradePnl, { color: pnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(pnl)}</Text>
                          {exitReason ? (
                            <Text style={[styles.tradeMeta, { color: exitColor, marginTop: 2 }]}>{exitReason.replace('_', ' ')}</Text>
                          ) : null}
                        </View>
                      </View>
                      <View style={styles.tradeBottom}>
                        <Text style={styles.tradeMeta}>Entry: {'\u20B9'}{Number(t.entry_price || 0).toFixed(2)}</Text>
                        <Text style={styles.tradeMeta}>Exit: {'\u20B9'}{Number(t.exit_price || t.ltp || 0).toFixed(2)}</Text>
                        <Text style={styles.tradeMeta}>x{t.quantity}</Text>
                        {(t.charges || 0) > 0 && (
                          <Text style={[styles.tradeMeta, { color: colors.yellow[400] + 'AA' }]}>Chg: {'\u20B9'}{t.charges.toFixed(0)}</Text>
                        )}
                      </View>
                    </View>
                  )
                })
              )}
            </Card>
          </>
        )}

        {tab === 'logs' && (
          <>
            {/* Log Level Filter */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 12, marginBottom: 8 }}>
              {LOG_FILTERS.map(f => (
                <TouchableOpacity key={f} onPress={() => setLogFilter(f)} style={[styles.filterBtn, logFilter === f && { backgroundColor: colors.violet[400] + '20', borderColor: colors.violet[400] + '40' }]}>
                  <Text style={[styles.filterText, logFilter === f && { color: colors.violet[400] }]}>{f}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <Card>
              <Text style={styles.label}>Logs ({filteredLogs.length})</Text>
              {filteredLogs.length === 0 ? (
                <Text style={styles.emptyText}>No log entries. Start trading to see activity.</Text>
              ) : (
                <View style={styles.logBox}>
                  {filteredLogs.slice(0, 100).map((entry, i) => {
                    const sourceColor = SOURCE_COLORS[entry.source] || colors.blue[400]
                    const levelColor = LOG_COLORS[entry.level] || colors.text.muted
                    return (
                      <View key={i} style={styles.logRow}>
                        <Text style={styles.logTime}>{entry.timestamp || ''}</Text>
                        <Text style={[styles.logLevel, { color: levelColor }]}>[{entry.level}]</Text>
                        <View style={[styles.logSourceBadge, { backgroundColor: sourceColor + '15' }]}>
                          <Text style={[styles.logSourceText, { color: sourceColor }]}>
                            {entry.source === 'auto' ? 'EQ-LV' : entry.source === 'paper' ? 'EQ-PP' :
                             entry.source === 'swing' ? 'EQ-SW' : entry.source === 'swing_paper' ? 'SW-PP' :
                             entry.source === 'options_auto' ? 'OPT-LV' : entry.source === 'options_paper' ? 'OPT-PP' :
                             entry.source === 'options_swing' ? 'OPT-SW' : entry.source === 'options_swing_paper' ? 'OPT-SP' :
                             entry.source || ''}
                          </Text>
                        </View>
                        <Text style={styles.logMsg} numberOfLines={2}>{entry.message}</Text>
                      </View>
                    )
                  })}
                </View>
              )}
            </Card>
          </>
        )}

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
  statsGrid: { flexDirection: 'row', gap: 8, marginTop: 12 },
  statCard: { flex: 1, backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[600], borderRadius: 12, padding: 10 },
  statLabel: { fontSize: 9, fontWeight: '600', color: colors.text.muted, marginBottom: 4 },
  statValue: { fontSize: 13, fontWeight: '800' },
  filterBtn: { backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[500], borderRadius: 8, paddingHorizontal: 12, paddingVertical: 5, marginRight: 6 },
  filterText: { fontSize: 11, fontWeight: '600', color: colors.text.muted },
  emptyText: { fontSize: 12, color: colors.text.dim, textAlign: 'center', paddingVertical: 20 },
  tradeRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.dark[600] },
  tradeTop: { flexDirection: 'row', justifyContent: 'space-between' },
  tradeSymbol: { fontSize: 14, fontWeight: '700', color: colors.text.primary },
  tradeMeta: { fontSize: 10, color: colors.text.muted },
  tradePnl: { fontSize: 14, fontWeight: '800' },
  tradeBottom: { flexDirection: 'row', gap: 10, marginTop: 4 },
  signalBadge: { paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  signalText: { fontSize: 9, fontWeight: '700' },
  sourceBadge: { paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  sourceText: { fontSize: 9, fontWeight: '600' },
  logBox: { backgroundColor: colors.dark[800], borderRadius: 8, padding: 8 },
  logRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 4, paddingVertical: 3 },
  logTime: { fontSize: 9, fontFamily: 'monospace', color: colors.text.dim, width: 46 },
  logLevel: { fontSize: 9, fontFamily: 'monospace', fontWeight: '700', width: 48 },
  logSourceBadge: { paddingHorizontal: 3, paddingVertical: 1, borderRadius: 3 },
  logSourceText: { fontSize: 8, fontWeight: '600' },
  logMsg: { fontSize: 9, color: colors.text.secondary, flex: 1 },
})
