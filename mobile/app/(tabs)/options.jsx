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
  startOptionsAutoTrading, stopOptionsAutoTrading, getOptionsAutoStatus,
  startOptionsPaperTrading, stopOptionsPaperTrading, getOptionsPaperStatus,
  startOptionsSwingTrading, stopOptionsSwingTrading, getOptionsSwingStatus,
  startOptionsSwingPaperTrading, stopOptionsSwingPaperTrading, getOptionsSwingPaperStatus,
  getMarketRegime,
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
  'intraday-live': { start: startOptionsAutoTrading, stop: stopOptionsAutoTrading, status: getOptionsAutoStatus, isLive: true },
  'intraday-paper': { start: startOptionsPaperTrading, stop: stopOptionsPaperTrading, status: getOptionsPaperStatus, isLive: false },
  'swing-live': { start: startOptionsSwingTrading, stop: stopOptionsSwingTrading, status: getOptionsSwingStatus, isLive: true },
  'swing-paper': { start: startOptionsSwingPaperTrading, stop: stopOptionsSwingPaperTrading, status: getOptionsSwingPaperStatus, isLive: false },
}

const CONVICTION_COLORS = {
  strongly_bullish: colors.green[400], mildly_bullish: colors.green[400],
  neutral: colors.yellow[400],
  mildly_bearish: colors.red[400], strongly_bearish: colors.red[400],
  high_volatility: colors.purple[400],
}

export default function OptionsScreen() {
  const [tab, setTab] = useState('intraday-live')
  const [capital, setCapital] = useState('25000')
  const [underlyings, setUnderlyings] = useState({ NIFTY: true, BANKNIFTY: false })
  const [loading, setLoading] = useState(false)

  const config = TAB_CONFIG[tab]
  const statusPoll = usePolling(config.status, POLL_INTERVAL)
  const regimePoll = usePolling(getMarketRegime, 60000)
  const status = statusPoll.data
  const running = status?.is_running ?? false
  const regime = regimePoll.data

  const accent = config.isLive ? colors.orange[400] : colors.blue[400]
  const selectedUnderlyings = Object.keys(underlyings).filter(k => underlyings[k])

  const handleStart = async () => {
    if (selectedUnderlyings.length === 0) return Alert.alert('Error', 'Select at least one underlying')
    const cap = parseFloat(capital)
    if (!cap || cap <= 0) return Alert.alert('Error', 'Enter valid capital')
    setLoading(true)
    try {
      const res = await config.start(cap, selectedUnderlyings)
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

  const positions = status?.active_positions || []
  const history = status?.trade_history || []
  const logs = status?.logs || []

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} refreshControl={<RefreshControl refreshing={false} onRefresh={statusPoll.refresh} tintColor={accent} />}>
        <Text style={styles.title}>Options Trading</Text>

        <TabBar tabs={TABS} active={tab} onSelect={setTab} />

        {/* Market Regime */}
        {regime && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Market Regime</Text>
            <View style={styles.regimeRow}>
              <Badge label={regime.conviction?.replace('_', ' ').toUpperCase() || 'UNKNOWN'} color={CONVICTION_COLORS[regime.conviction] || colors.text.muted} />
              <Text style={styles.regimeMeta}>VIX: {regime.components?.vix?.toFixed(1) || '--'} | PCR: {regime.components?.pcr?.toFixed(2) || '--'}</Text>
            </View>
            {regime.recommended_strategies?.length > 0 && (
              <View style={styles.recRow}>
                <Text style={styles.recLabel}>Recommended:</Text>
                {regime.recommended_strategies.map(s => (
                  <Badge key={s} label={STRATEGY_NAMES[s] || s} color={colors.violet[400]} small />
                ))}
              </View>
            )}
          </Card>
        )}

        {/* Capital */}
        <Card style={{ marginTop: 12 }}>
          <Text style={styles.label}>Capital</Text>
          <TextInput
            style={styles.input}
            value={capital}
            onChangeText={setCapital}
            keyboardType="numeric"
            editable={!running}
            placeholderTextColor={colors.text.dim}
          />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
            {CAPITAL_PRESETS.map(p => (
              <TouchableOpacity key={p} onPress={() => !running && setCapital(String(p))} style={[styles.preset, capital === String(p) && { borderColor: accent }]}>
                <Text style={[styles.presetText, capital === String(p) && { color: accent }]}>{p >= 100000 ? `${p/100000}L` : `${p/1000}K`}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </Card>

        {/* Underlying Selector */}
        {!running && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Underlyings</Text>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              {['NIFTY', 'BANKNIFTY'].map(u => (
                <TouchableOpacity key={u} onPress={() => setUnderlyings(prev => ({ ...prev, [u]: !prev[u] }))}
                  style={[styles.underBtn, underlyings[u] && { backgroundColor: accent + '20', borderColor: accent + '40' }]}>
                  <Text style={[styles.underText, underlyings[u] && { color: accent }]}>{u}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </Card>
        )}

        {/* Start / Stop */}
        <View style={{ marginTop: 12 }}>
          {running ? (
            <Button title="Stop Trading" onPress={handleStop} color={colors.red[500]} loading={loading} />
          ) : (
            <Button title="Start Trading" onPress={handleStart} color={accent} loading={loading} disabled={selectedUnderlyings.length === 0} />
          )}
        </View>

        {/* Running Status */}
        {running && (
          <Card style={{ marginTop: 12 }}>
            <View style={styles.statusHeader}>
              <View style={styles.statusDot} />
              <Text style={[styles.statusTextLbl, { color: accent }]}>Running</Text>
            </View>
            <View style={styles.statsRow}>
              <View style={styles.stat}><Text style={styles.statLabel}>P&L</Text><Text style={[styles.statValue, { color: (status?.total_pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(status?.total_pnl || 0)}</Text></View>
              <View style={styles.stat}><Text style={styles.statLabel}>Scans</Text><Text style={styles.statValue}>{status?.scan_count || 0}</Text></View>
              <View style={styles.stat}><Text style={styles.statLabel}>Positions</Text><Text style={styles.statValue}>{positions.length}</Text></View>
            </View>
          </Card>
        )}

        {/* Positions */}
        {positions.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <Text style={styles.label}>Active Positions ({positions.length})</Text>
            {positions.map((p, i) => (
              <View key={i} style={styles.posRow}>
                <View>
                  <Text style={styles.posSymbol}>{p.underlying || '--'}</Text>
                  <Text style={styles.posMeta}>{STRATEGY_NAMES[p.strategy] || p.spread_type || '--'}</Text>
                  <Text style={styles.posMeta}>{(p.legs || []).map(l => l.symbol?.split(':')[1] || '').join(' / ')}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={[styles.posPnl, { color: (p.pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(p.pnl || 0)}</Text>
                  <Text style={styles.posMeta}>Premium: {'\u20B9'}{(p.net_premium || 0).toFixed(0)}</Text>
                </View>
              </View>
            ))}
          </Card>
        )}

        {/* Logs */}
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
  underBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.dark[500], alignItems: 'center', backgroundColor: colors.dark[800] },
  underText: { fontSize: 14, fontWeight: '700', color: colors.text.muted },
  regimeRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  regimeMeta: { fontSize: 11, color: colors.text.muted },
  recRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  recLabel: { fontSize: 10, color: colors.text.muted },
  statusHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.green[400] },
  statusTextLbl: { fontSize: 13, fontWeight: '700' },
  statsRow: { flexDirection: 'row', justifyContent: 'space-around' },
  stat: { alignItems: 'center' },
  statLabel: { fontSize: 10, color: colors.text.muted },
  statValue: { fontSize: 15, fontWeight: '700', color: colors.text.primary, marginTop: 2 },
  posRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.dark[600] },
  posSymbol: { fontSize: 14, fontWeight: '700', color: colors.text.primary },
  posMeta: { fontSize: 10, color: colors.text.muted, marginTop: 2 },
  posPnl: { fontSize: 14, fontWeight: '700' },
  logBox: { backgroundColor: colors.dark[800], borderRadius: 8, padding: 10, maxHeight: 200 },
  logLine: { fontSize: 10, fontFamily: 'monospace', lineHeight: 16 },
})
