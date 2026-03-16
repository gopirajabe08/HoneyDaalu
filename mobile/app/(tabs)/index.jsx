import React, { useState, useCallback } from 'react'
import { View, Text, ScrollView, RefreshControl, StyleSheet } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Activity, Wifi, WifiOff, TrendingUp, TrendingDown } from 'lucide-react-native'
import { colors } from '../../src/theme/colors'
import Card from '../../src/components/common/Card'
import MetricCard from '../../src/components/common/MetricCard'
import Badge from '../../src/components/common/Badge'
import { usePolling } from '../../src/hooks/usePolling'
import { getFyersStatus, getFyersFunds, getPositions } from '../../src/services/api'
import { getAutoStatus, getPaperStatus, getOptionsAutoStatus, getOptionsPaperStatus, getDailyPnl } from '../../src/services/api'
import { formatINR } from '../../src/utils/formatters'
import { POLL_INTERVAL } from '../../src/utils/constants'

export default function Dashboard() {
  const [refreshing, setRefreshing] = useState(false)

  const fyers = usePolling(getFyersStatus, POLL_INTERVAL)
  const funds = usePolling(getFyersFunds, POLL_INTERVAL)
  const positions = usePolling(getPositions, POLL_INTERVAL)
  const autoStatus = usePolling(getAutoStatus, POLL_INTERVAL)
  const paperStatus = usePolling(getPaperStatus, POLL_INTERVAL)
  const optAutoStatus = usePolling(getOptionsAutoStatus, POLL_INTERVAL)
  const optPaperStatus = usePolling(getOptionsPaperStatus, POLL_INTERVAL)
  const dailyPnl = usePolling(useCallback(() => getDailyPnl(30, 'live'), []), POLL_INTERVAL)

  const onRefresh = async () => {
    setRefreshing(true)
    await Promise.all([fyers.refresh(), funds.refresh(), positions.refresh(), autoStatus.refresh(), paperStatus.refresh(), optAutoStatus.refresh(), dailyPnl.refresh()])
    setRefreshing(false)
  }

  const isConnected = fyers.data?.connected === true || fyers.data?.authenticated === true
  const fundList = funds.data?.fund_limit || []
  const getFundVal = (id) => { const f = fundList.find(x => x.id === id); return f ? (f.equityAmount || 0) : 0 }
  const totalBal = getFundVal(1)
  const availBal = getFundVal(10)
  const startOfDay = getFundVal(9)
  const fundTransfer = getFundVal(6)
  const todayPnl = getFundVal(4)

  const posData = positions.data?.netPositions || positions.data?.data?.netPositions || []
  const traded = posData.filter(p => (p.buyQty || 0) > 0 || (p.sellQty || 0) > 0)
  const realizedPnl = traded.filter(p => (p.netQty || 0) === 0).reduce((s, p) => s + (p.realized_profit || 0), 0)
  const unrealizedPnl = traded.filter(p => (p.netQty || 0) !== 0).reduce((s, p) => s + (p.unrealized_profit || 0), 0)
  const openPositions = traded.filter(p => (p.netQty || 0) !== 0)

  const engines = [
    { name: 'Equity Live', running: autoStatus.data?.is_running, pnl: autoStatus.data?.total_pnl, color: colors.orange[400] },
    { name: 'Equity Paper', running: paperStatus.data?.is_running, pnl: paperStatus.data?.total_pnl, color: colors.blue[400] },
    { name: 'Options Live', running: optAutoStatus.data?.is_running, pnl: optAutoStatus.data?.total_pnl, color: colors.purple[400] },
    { name: 'Options Paper', running: optPaperStatus.data?.is_running, pnl: optPaperStatus.data?.total_pnl, color: colors.cyan[400] },
  ]
  const runningEngines = engines.filter(e => e.running)

  // Cumulative P&L from daily data
  const pnlRows = Array.isArray(dailyPnl.data) ? dailyPnl.data : []
  const cumPnl = pnlRows.reduce((s, d) => s + (d.net_pnl || d.total_pnl || 0), 0)

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.orange[400]} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>IntraTrading</Text>
          <View style={styles.statusRow}>
            {isConnected ? <Wifi size={14} color={colors.green[400]} /> : <WifiOff size={14} color={colors.red[400]} />}
            <Text style={[styles.statusText, { color: isConnected ? colors.green[400] : colors.red[400] }]}>
              {isConnected ? 'Fyers Connected' : 'Not Connected'}
            </Text>
          </View>
        </View>

        {/* Funds Overview */}
        <Card style={{ marginBottom: 12 }}>
          <Text style={styles.sectionTitle}>Account</Text>
          <View style={styles.fundsGrid}>
            <View style={styles.fundItem}>
              <Text style={styles.fundLabel}>Available</Text>
              <Text style={styles.fundValue}>{'\u20B9'}{availBal.toLocaleString('en-IN')}</Text>
            </View>
            <View style={styles.fundItem}>
              <Text style={styles.fundLabel}>Start of Day</Text>
              <Text style={styles.fundValue}>{'\u20B9'}{startOfDay.toLocaleString('en-IN')}</Text>
            </View>
            <View style={styles.fundItem}>
              <Text style={styles.fundLabel}>Fund Transfer</Text>
              <Text style={[styles.fundValue, { color: fundTransfer > 0 ? colors.blue[400] : colors.text.secondary }]}>
                {fundTransfer > 0 ? '+' : ''}{'\u20B9'}{fundTransfer.toLocaleString('en-IN')}
              </Text>
            </View>
            <View style={styles.fundItem}>
              <Text style={styles.fundLabel}>Today P&L</Text>
              <Text style={[styles.fundValue, { color: todayPnl >= 0 ? colors.green[400] : colors.red[400] }]}>
                {formatINR(todayPnl)}
              </Text>
            </View>
          </View>
        </Card>

        {/* Running Engines */}
        {runningEngines.length > 0 && (
          <Card style={{ marginBottom: 12 }}>
            <Text style={styles.sectionTitle}>Active Engines</Text>
            {runningEngines.map(e => (
              <View key={e.name} style={styles.engineRow}>
                <View style={styles.engineLeft}>
                  <View style={[styles.dot, { backgroundColor: e.color }]} />
                  <Text style={[styles.engineName, { color: e.color }]}>{e.name}</Text>
                </View>
                <Text style={[styles.enginePnl, { color: (e.pnl || 0) >= 0 ? colors.green[400] : colors.red[400] }]}>
                  {formatINR(e.pnl || 0)}
                </Text>
              </View>
            ))}
          </Card>
        )}

        {/* Metrics */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
          <MetricCard label="Realized P&L" value={formatINR(realizedPnl)} valueColor={realizedPnl >= 0 ? colors.green[400] : colors.red[400]} />
          <MetricCard label="Unrealized" value={formatINR(unrealizedPnl)} valueColor={unrealizedPnl >= 0 ? colors.green[400] : colors.red[400]} />
          <MetricCard label="Open Positions" value={`${openPositions.length}`} />
          <MetricCard label="Total Balance" value={`\u20B9${totalBal.toLocaleString('en-IN')}`} />
          <MetricCard label="Cumulative P&L" value={formatINR(cumPnl)} valueColor={cumPnl >= 0 ? colors.green[400] : colors.red[400]} sub={`Last ${pnlRows.length} days`} />
        </ScrollView>

        {/* Open Positions */}
        <Card>
          <Text style={styles.sectionTitle}>Open Positions ({openPositions.length})</Text>
          {openPositions.length === 0 ? (
            <Text style={styles.emptyText}>No open positions</Text>
          ) : (
            openPositions.map((p, i) => {
              const sym = (p.symbol || '').replace('NSE:', '').replace('-EQ', '')
              const pnl = p.unrealized_profit || 0
              const qty = p.netQty || 0
              return (
                <View key={i} style={styles.posRow}>
                  <View>
                    <Text style={styles.posSymbol}>{sym}</Text>
                    <Text style={styles.posQty}>{qty > 0 ? 'LONG' : 'SHORT'} x{Math.abs(qty)} @ {'\u20B9'}{(p.buyAvg || p.sellAvg || 0).toFixed(2)}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={[styles.posPnl, { color: pnl >= 0 ? colors.green[400] : colors.red[400] }]}>{formatINR(pnl)}</Text>
                    <Text style={styles.posLtp}>LTP {'\u20B9'}{(p.ltp || 0).toFixed(2)}</Text>
                  </View>
                </View>
              )
            })
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
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  title: { fontSize: 22, fontWeight: '800', color: colors.text.primary },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusText: { fontSize: 11, fontWeight: '600' },
  sectionTitle: { fontSize: 12, fontWeight: '700', color: colors.text.secondary, marginBottom: 10 },
  fundsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  fundItem: { width: '46%' },
  fundLabel: { fontSize: 10, color: colors.text.muted, marginBottom: 2 },
  fundValue: { fontSize: 15, fontWeight: '700', color: colors.text.primary },
  engineRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.dark[600] },
  engineLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  engineName: { fontSize: 13, fontWeight: '600' },
  enginePnl: { fontSize: 13, fontWeight: '700' },
  emptyText: { fontSize: 12, color: colors.text.dim, textAlign: 'center', paddingVertical: 20 },
  posRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.dark[600] },
  posSymbol: { fontSize: 14, fontWeight: '700', color: colors.text.primary },
  posQty: { fontSize: 11, color: colors.text.muted, marginTop: 2 },
  posPnl: { fontSize: 14, fontWeight: '700' },
  posLtp: { fontSize: 10, color: colors.text.muted, marginTop: 2 },
})
