import React, { useState, useEffect } from 'react'
import { View, Text, ScrollView, TextInput, TouchableOpacity, RefreshControl, StyleSheet, Alert } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { colors } from '../../src/theme/colors'
import Card from '../../src/components/common/Card'
import Badge from '../../src/components/common/Badge'
import Button from '../../src/components/common/Button'
import TabBar from '../../src/components/common/TabBar'
import { usePolling } from '../../src/hooks/usePolling'
import {
  getFuturesStrategies,
  startFuturesAutoTrading, stopFuturesAutoTrading, getFuturesAutoStatus,
  startFuturesPaperTrading, stopFuturesPaperTrading, getFuturesPaperStatus,
  startFuturesSwingTrading, stopFuturesSwingTrading, getFuturesSwingStatus,
  startFuturesSwingPaperTrading, stopFuturesSwingPaperTrading, getFuturesSwingPaperStatus,
  startFuturesAutoRegime, startFuturesPaperRegime, startFuturesSwingRegime, startFuturesSwingPaperRegime,
} from '../../src/services/api'
import { formatINR } from '../../src/utils/formatters'
import { LOG_COLORS, POLL_INTERVAL, STRATEGY_NAMES } from '../../src/utils/constants'
import { CAPITAL_PRESETS } from '../../src/data/strategies'

const TABS = [
  { id: 'intraday-live', label: 'Intraday Live', activeColor: colors.orange[400] },
  { id: 'intraday-paper', label: 'Intraday Paper', activeColor: colors.blue[400] },
  { id: 'swing-live', label: 'Swing Live', activeColor: colors.emerald[400] },
  { id: 'swing-paper', label: 'Swing Paper', activeColor: colors.teal[400] },
]

const TAB_CONFIG = {
  'intraday-live': { start: startFuturesAutoTrading, stop: stopFuturesAutoTrading, status: getFuturesAutoStatus, autoStart: startFuturesAutoRegime, isLive: true, isSwing: false },
  'intraday-paper': { start: startFuturesPaperTrading, stop: stopFuturesPaperTrading, status: getFuturesPaperStatus, autoStart: startFuturesPaperRegime, isLive: false, isSwing: false },
  'swing-live': { start: startFuturesSwingTrading, stop: stopFuturesSwingTrading, status: getFuturesSwingStatus, autoStart: startFuturesSwingRegime, isLive: true, isSwing: true },
  'swing-paper': { start: startFuturesSwingPaperTrading, stop: stopFuturesSwingPaperTrading, status: getFuturesSwingPaperStatus, autoStart: startFuturesSwingPaperRegime, isLive: false, isSwing: true },
}

const OI_COLORS = {
  long_buildup: colors.green[400],
  short_covering: colors.emerald[400],
  short_buildup: colors.red[400],
  long_unwinding: colors.orange[400],
}

export default function FuturesScreen() {
  const [tab, setTab] = useState('intraday-live')
  const [capital, setCapital] = useState('100000')
  const [strategies, setStrategies] = useState([])
  const [selectedStrategies, setSelectedStrategies] = useState({})
  const [loading, setLoading] = useState(false)
  const [autoMode, setAutoMode] = useState(true)

  const config = TAB_CONFIG[tab]
  const statusPoll = usePolling(config.status, POLL_INTERVAL)
  const status = statusPoll.data
  const running = status?.is_running ?? false
  const accent = config.isLive ? colors.orange[400] : colors.blue[400]

  // Load strategies once
  useEffect(() => {
    getFuturesStrategies().then(data => {
      if (Array.isArray(data)) {
        setStrategies(data)
        const sel = {}
        data.forEach(s => {
          const tfs = s.timeframes || []
          sel[s.id] = { selected: true, timeframe: tfs[0] || '15m' }
        })
        setSelectedStrategies(sel)
      }
    }).catch(() => {})
  }, [])

  const handleStart = async () => {
    const cap = parseFloat(capital)
    if (!cap || cap <= 0) return Alert.alert('Error', 'Enter valid capital')
    setLoading(true)
    try {
      let res
      if (autoMode && config.autoStart) {
        res = await config.autoStart(cap)
      } else {
        const strats = Object.entries(selectedStrategies)
          .filter(([, v]) => v.selected)
          .map(([key, v]) => ({ strategy: key, timeframe: v.timeframe }))
        if (strats.length === 0) { setLoading(false); return Alert.alert('Error', 'Select at least one strategy') }
        res = config.isSwing ? await config.start(strats, cap, 240) : await config.start(strats, cap)
      }
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

  const positions = status?.active_trades || []
  const history = status?.trade_history || []
  const logs = status?.logs || []

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} refreshControl={<RefreshControl refreshing={false} onRefresh={statusPoll.refresh} tintColor={accent} />}>
        <Text style={styles.title}>Futures Trading</Text>

        <TabBar tabs={TABS} active={tab} onSelect={setTab} />

        {/* Strategy Selection */}
        {!running && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Strategies</Text>
            {strategies.map(s => {
              const sel = selectedStrategies[s.id]
              const checked = sel?.selected ?? false
              return (
                <TouchableOpacity
                  key={s.id}
                  style={[styles.stratRow, checked && { borderColor: accent }]}
                  onPress={() => setSelectedStrategies(prev => ({
                    ...prev,
                    [s.id]: { ...prev[s.id], selected: !checked },
                  }))}
                >
                  <View style={styles.stratHeader}>
                    <Text style={[styles.stratName, checked && { color: accent }]}>{s.name}</Text>
                    <View style={[styles.checkbox, checked && { backgroundColor: accent, borderColor: accent }]}>
                      {checked && <Text style={styles.checkmark}>✓</Text>}
                    </View>
                  </View>
                  <Text style={styles.stratDesc}>{s.description}</Text>
                </TouchableOpacity>
              )
            })}

            <Text style={[styles.label, { marginTop: 12 }]}>Capital (₹)</Text>
            <TextInput
              style={styles.input}
              value={capital}
              onChangeText={setCapital}
              keyboardType="numeric"
              placeholder="200000"
              placeholderTextColor={colors.text.muted}
            />
            <View style={styles.presets}>
              {CAPITAL_PRESETS.map(p => (
                <TouchableOpacity key={p} style={styles.presetBtn} onPress={() => setCapital(String(p))}>
                  <Text style={styles.presetText}>{p >= 100000 ? `${p/100000}L` : `${p/1000}K`}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </Card>
        )}

        {/* Start / Stop */}
        <View style={{ marginTop: 12, flexDirection: 'row', gap: 10 }}>
          {!running ? (
            <Button
              title={`Start ${config.isLive ? 'Live' : 'Paper'} ${config.isSwing ? 'Swing' : 'Intraday'}`}
              onPress={handleStart}
              loading={loading}
              color={accent}
            />
          ) : (
            <Button title="Stop Trading" onPress={handleStop} loading={loading} color={colors.red[400]} />
          )}
        </View>

        {/* Stats */}
        {status && (
          <View style={styles.statsRow}>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>Scans</Text>
              <Text style={styles.statValue}>{status.scan_count || 0}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>Orders</Text>
              <Text style={styles.statValue}>{status.order_count || 0}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>P&L</Text>
              <Text style={[styles.statValue, { color: (status.total_pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>
                {formatINR(status.total_pnl || 0)}
              </Text>
            </View>
          </View>
        )}

        {/* Active Positions */}
        {positions.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Active Positions</Text>
            {positions.map((t, i) => (
              <View key={i} style={styles.tradeRow}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Text style={{ color: t.side === 1 ? colors.green[400] : colors.red[400], fontSize: 11, fontWeight: '700' }}>{t.signal_type}</Text>
                  <Text style={{ color: colors.text.primary, fontSize: 13, fontWeight: '600' }}>{t.symbol}</Text>
                  {t.oi_sentiment && (
                    <Badge label={t.oi_sentiment.replace('_', ' ')} color={OI_COLORS[t.oi_sentiment] || colors.text.muted} />
                  )}
                </View>
                <Text style={{ color: (t.pnl || 0) >= 0 ? colors.green[400] : colors.red[400], fontSize: 12, fontWeight: '600' }}>
                  {formatINR(t.pnl || 0)}
                </Text>
              </View>
            ))}
          </Card>
        )}

        {/* Trade History */}
        {history.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Recent Trades</Text>
            {history.slice(-10).reverse().map((t, i) => (
              <View key={i} style={styles.tradeRow}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Text style={{ color: t.side === 1 ? colors.green[400] : colors.red[400], fontSize: 11 }}>{t.signal_type}</Text>
                  <Text style={{ color: colors.text.primary, fontSize: 12 }}>{t.symbol}</Text>
                  <Text style={{ color: colors.text.muted, fontSize: 10 }}>{t.exit_reason}</Text>
                </View>
                <Text style={{ color: (t.pnl || 0) >= 0 ? colors.green[400] : colors.red[400], fontSize: 11, fontWeight: '600' }}>
                  {formatINR(t.pnl || 0)}
                </Text>
              </View>
            ))}
          </Card>
        )}

        {/* Logs */}
        {logs.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Logs</Text>
            {logs.slice(-30).map((log, i) => (
              <View key={i} style={{ flexDirection: 'row', gap: 6, marginBottom: 2 }}>
                <Text style={{ color: colors.text.muted, fontSize: 9 }}>{log.time?.split('T')[1]?.substring(0, 8) || ''}</Text>
                <Text style={{ color: LOG_COLORS[log.level] || colors.text.muted, fontSize: 9, fontWeight: '600', width: 55 }}>[{log.level}]</Text>
                <Text style={{ color: colors.text.secondary, fontSize: 9, flex: 1 }}>{log.message}</Text>
              </View>
            ))}
          </Card>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.dark[900] },
  scroll: { flex: 1, paddingHorizontal: 16, paddingTop: 16 },
  title: { color: colors.text.primary, fontSize: 22, fontWeight: '700', marginBottom: 12 },
  label: { color: colors.text.secondary, fontSize: 12, fontWeight: '600', marginBottom: 8 },
  stratRow: {
    backgroundColor: colors.dark[700],
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.dark[500],
  },
  stratHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  stratName: { color: colors.text.primary, fontSize: 13, fontWeight: '600' },
  stratDesc: { color: colors.text.muted, fontSize: 10 },
  checkbox: {
    width: 18, height: 18, borderRadius: 4,
    borderWidth: 1.5, borderColor: colors.dark[400],
    alignItems: 'center', justifyContent: 'center',
  },
  checkmark: { color: 'white', fontSize: 11, fontWeight: '700' },
  input: {
    backgroundColor: colors.dark[700],
    borderRadius: 8,
    padding: 10,
    color: colors.text.primary,
    fontSize: 14,
    borderWidth: 1,
    borderColor: colors.dark[500],
  },
  presets: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  presetBtn: {
    backgroundColor: colors.dark[600],
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  presetText: { color: colors.text.secondary, fontSize: 11, fontWeight: '600' },
  statsRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  statBox: {
    flex: 1,
    backgroundColor: colors.dark[700],
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.dark[500],
  },
  statLabel: { color: colors.text.muted, fontSize: 10, marginBottom: 4 },
  statValue: { color: colors.text.primary, fontSize: 16, fontWeight: '700' },
  tradeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.dark[700],
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 6,
  },
})
