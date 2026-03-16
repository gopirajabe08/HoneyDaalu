import React, { useState, useEffect, useCallback } from 'react'
import { View, Text, ScrollView, TextInput, TouchableOpacity, FlatList, RefreshControl, StyleSheet, Alert } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Play, Square, Activity } from 'lucide-react-native'
import { colors } from '../../src/theme/colors'
import Card from '../../src/components/common/Card'
import Badge from '../../src/components/common/Badge'
import Button from '../../src/components/common/Button'
import TabBar from '../../src/components/common/TabBar'
import { usePolling } from '../../src/hooks/usePolling'
import {
  startAutoTrading, stopAutoTrading, getAutoStatus,
  startPaperTrading, stopPaperTrading, getPaperStatus,
  startSwingTrading, stopSwingTrading, getSwingStatus,
  startSwingPaperTrading, stopSwingPaperTrading, getSwingPaperStatus,
} from '../../src/services/api'
import { formatINR, formatTime } from '../../src/utils/formatters'
import { STRATEGY_NAMES, LOG_COLORS, POLL_INTERVAL } from '../../src/utils/constants'
import { strategies, CAPITAL_PRESETS } from '../../src/data/strategies'

const TABS = [
  { id: 'intraday-live', label: 'Intraday Live', activeColor: colors.orange[400] },
  { id: 'intraday-paper', label: 'Intraday Paper', activeColor: colors.blue[400] },
  { id: 'swing-live', label: 'Swing Live', activeColor: colors.emerald[400] },
  { id: 'swing-paper', label: 'Swing Paper', activeColor: colors.teal[400] },
]

const TAB_CONFIG = {
  'intraday-live': { start: startAutoTrading, stop: stopAutoTrading, status: getAutoStatus, isLive: true, isSwing: false },
  'intraday-paper': { start: startPaperTrading, stop: stopPaperTrading, status: getPaperStatus, isLive: false, isSwing: false },
  'swing-live': { start: startSwingTrading, stop: stopSwingTrading, status: getSwingStatus, isLive: true, isSwing: true },
  'swing-paper': { start: startSwingPaperTrading, stop: stopSwingPaperTrading, status: getSwingPaperStatus, isLive: false, isSwing: true },
}

export default function EquityScreen() {
  const [tab, setTab] = useState('intraday-live')
  const [capital, setCapital] = useState('75000')
  const [selected, setSelected] = useState({ play3_vwap_pullback: '5m', play4_supertrend: '5m' })
  const [loading, setLoading] = useState(false)

  const config = TAB_CONFIG[tab]
  const statusPoll = usePolling(config.status, POLL_INTERVAL)
  const status = statusPoll.data
  const running = status?.is_running ?? false

  // Reset selections on tab change
  useEffect(() => {
    if (tab === 'intraday-live') setSelected({ play3_vwap_pullback: '5m', play4_supertrend: '5m' })
    else if (tab === 'intraday-paper') setSelected({ play1_ema_crossover: '15m', play6_bb_contra: '15m' })
    else setSelected({})
  }, [tab])

  const toggleStrategy = (id, tf) => {
    setSelected(prev => {
      if (prev[id]) { const n = { ...prev }; delete n[id]; return n }
      return { ...prev, [id]: tf }
    })
  }

  const setTimeframe = (id, tf) => {
    setSelected(prev => ({ ...prev, [id]: tf }))
  }

  const handleStart = async () => {
    const strats = Object.entries(selected).map(([strategy, timeframe]) => ({ strategy, timeframe }))
    if (strats.length === 0) return Alert.alert('Error', 'Select at least one strategy')
    const cap = parseFloat(capital)
    if (!cap || cap <= 0) return Alert.alert('Error', 'Enter valid capital')
    setLoading(true)
    try {
      const res = await config.start(strats, cap)
      if (res?.error) Alert.alert('Error', res.error)
      else statusPoll.refresh()
    } catch (e) { Alert.alert('Error', e.message) }
    setLoading(false)
  }

  const handleStop = async () => {
    Alert.alert('Stop Trading', 'Are you sure?', [
      { text: 'Cancel' },
      { text: 'Stop', style: 'destructive', onPress: async () => {
        setLoading(true)
        try { await config.stop(); statusPoll.refresh() } catch {}
        setLoading(false)
      }},
    ])
  }

  const accent = config.isLive ? colors.orange[400] : colors.blue[400]
  const activeTrades = status?.active_trades || []
  const tradeHistory = status?.trade_history || []
  const logs = status?.logs || []

  // Filter strategies for paper mode (hide proven ones)
  const visibleStrategies = (!config.isLive && !config.isSwing)
    ? strategies.filter(s => !['play3_vwap_pullback', 'play4_supertrend'].includes(s.id))
    : strategies

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} refreshControl={<RefreshControl refreshing={false} onRefresh={statusPoll.refresh} tintColor={accent} />}>
        <Text style={styles.title}>Equity Trading</Text>

        <TabBar tabs={TABS} active={tab} onSelect={setTab} />

        {/* Capital Input */}
        <Card style={{ marginTop: 12 }}>
          <Text style={styles.label}>Capital</Text>
          <TextInput
            style={styles.input}
            value={capital}
            onChangeText={setCapital}
            keyboardType="numeric"
            placeholder="Enter capital"
            placeholderTextColor={colors.text.dim}
            editable={!running}
          />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
            {CAPITAL_PRESETS.map(p => (
              <TouchableOpacity key={p} onPress={() => !running && setCapital(String(p))} style={[styles.preset, capital === String(p) && { borderColor: accent }]}>
                <Text style={[styles.presetText, capital === String(p) && { color: accent }]}>{p >= 100000 ? `${p/100000}L` : `${p/1000}K`}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </Card>

        {/* Strategy Selection */}
        {!running && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Strategies</Text>
            {visibleStrategies.map(strat => {
              const isSelected = !!selected[strat.id]
              return (
                <View key={strat.id} style={[styles.stratRow, isSelected && { borderColor: accent + '40' }]}>
                  <TouchableOpacity style={styles.stratHeader} onPress={() => toggleStrategy(strat.id, strat.timeframes[0])}>
                    <View style={[styles.checkbox, isSelected && { backgroundColor: accent, borderColor: accent }]}>
                      {isSelected && <Text style={{ color: '#fff', fontSize: 10, fontWeight: '800' }}>✓</Text>}
                    </View>
                    <View>
                      <Text style={styles.stratName}>{strat.short} — {strat.name}</Text>
                    </View>
                  </TouchableOpacity>
                  {isSelected && strat.timeframes.length > 1 && (
                    <View style={styles.tfRow}>
                      {strat.timeframes.map(tf => (
                        <TouchableOpacity key={tf} onPress={() => setTimeframe(strat.id, tf)} style={[styles.tfBtn, selected[strat.id] === tf && { backgroundColor: accent + '20', borderColor: accent + '40' }]}>
                          <Text style={[styles.tfText, selected[strat.id] === tf && { color: accent }]}>{tf}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}
                </View>
              )
            })}
          </Card>
        )}

        {/* Start / Stop */}
        <View style={{ marginTop: 12 }}>
          {running ? (
            <Button title="Stop Trading" onPress={handleStop} color={colors.red[500]} loading={loading} />
          ) : (
            <Button title="Start Trading" onPress={handleStart} color={accent} loading={loading} disabled={Object.keys(selected).length === 0} />
          )}
        </View>

        {/* Running Status */}
        {running && (
          <Card style={{ marginTop: 12 }}>
            <View style={styles.statusHeader}>
              <View style={styles.statusDot} />
              <Text style={[styles.statusText, { color: accent }]}>Running</Text>
            </View>
            <View style={styles.statsRow}>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>P&L</Text>
                <Text style={[styles.statValue, { color: (status?.total_pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(status?.total_pnl || 0)}</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>Scans</Text>
                <Text style={styles.statValue}>{status?.scan_count || 0}</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>Orders</Text>
                <Text style={styles.statValue}>{status?.order_count || 0}</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>Positions</Text>
                <Text style={styles.statValue}>{activeTrades.length}</Text>
              </View>
            </View>
          </Card>
        )}

        {/* Active Trades */}
        {activeTrades.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Active Trades ({activeTrades.length})</Text>
            {activeTrades.map((t, i) => (
              <View key={i} style={styles.tradeRow}>
                <View>
                  <Text style={styles.tradeSymbol}>{t.symbol}</Text>
                  <Text style={styles.tradeMeta}>{STRATEGY_NAMES[t.strategy] || t.strategy} · {t.signal_type} x{t.quantity}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={[styles.tradePnl, { color: (t.pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(t.pnl || 0)}</Text>
                  <Text style={styles.tradeMeta}>Entry {'\u20B9'}{t.entry_price}</Text>
                </View>
              </View>
            ))}
          </Card>
        )}

        {/* Trade History */}
        {tradeHistory.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Completed ({tradeHistory.length})</Text>
            {tradeHistory.slice(-10).reverse().map((t, i) => (
              <View key={i} style={styles.tradeRow}>
                <View>
                  <Text style={styles.tradeSymbol}>{t.symbol}</Text>
                  <Text style={styles.tradeMeta}>{t.exit_reason}</Text>
                </View>
                <Text style={[styles.tradePnl, { color: (t.pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(t.pnl || 0)}</Text>
              </View>
            ))}
          </Card>
        )}

        {/* Engine Logs */}
        {logs.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Engine Logs</Text>
            <View style={styles.logBox}>
              {logs.slice(-20).reverse().map((log, i) => (
                <Text key={i} style={[styles.logLine, { color: LOG_COLORS[log.level] || colors.text.muted }]}>
                  {log.time?.substring(11, 19)} [{log.level}] {log.message}
                </Text>
              ))}
            </View>
          </Card>
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
  input: { backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[500], borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, color: colors.text.primary, fontSize: 16, fontWeight: '700' },
  preset: { backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[500], borderRadius: 8, paddingHorizontal: 14, paddingVertical: 6, marginRight: 8 },
  presetText: { fontSize: 12, fontWeight: '600', color: colors.text.muted },
  stratRow: { backgroundColor: colors.dark[800], borderWidth: 1, borderColor: colors.dark[600], borderRadius: 12, marginBottom: 8, padding: 12 },
  stratHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  checkbox: { width: 20, height: 20, borderRadius: 6, borderWidth: 2, borderColor: colors.dark[500], alignItems: 'center', justifyContent: 'center' },
  stratName: { fontSize: 13, fontWeight: '600', color: colors.text.primary },
  tfRow: { flexDirection: 'row', gap: 6, marginTop: 8, marginLeft: 30 },
  tfBtn: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, borderWidth: 1, borderColor: colors.dark[500] },
  tfText: { fontSize: 11, fontWeight: '600', color: colors.text.muted },
  statusHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.green[400] },
  statusText: { fontSize: 13, fontWeight: '700' },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  stat: { alignItems: 'center' },
  statLabel: { fontSize: 10, color: colors.text.muted },
  statValue: { fontSize: 15, fontWeight: '700', color: colors.text.primary, marginTop: 2 },
  tradeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.dark[600] },
  tradeSymbol: { fontSize: 13, fontWeight: '700', color: colors.text.primary },
  tradeMeta: { fontSize: 10, color: colors.text.muted, marginTop: 2 },
  tradePnl: { fontSize: 13, fontWeight: '700' },
  logBox: { backgroundColor: colors.dark[800], borderRadius: 8, padding: 10, maxHeight: 200 },
  logLine: { fontSize: 10, fontFamily: 'monospace', lineHeight: 16 },
})
