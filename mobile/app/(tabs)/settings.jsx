import React, { useState, useEffect } from 'react'
import { View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, Alert } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { colors } from '../../src/theme/colors'
import Card from '../../src/components/common/Card'
import { loadSavedIp, saveServerIp, getApiBase, apiFetch } from '../../src/services/api'

export default function SettingsScreen() {
  const [ip, setIp] = useState('')
  const [status, setStatus] = useState(null) // null | 'connected' | 'failed'
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    loadSavedIp().then(setIp)
  }, [])

  const testConnection = async (testIp) => {
    const target = testIp || ip
    if (!target) return Alert.alert('Error', 'Enter server IP')
    setTesting(true)
    setStatus(null)
    try {
      const url = `http://${target}:8001/api/fyers/status`
      const res = await fetch(url, { timeout: 5000 })
      const data = await res.json()
      if (data.connected || data.configured) {
        setStatus('connected')
        await saveServerIp(target)
        setIp(target)
      } else {
        setStatus('failed')
      }
    } catch {
      setStatus('failed')
    }
    setTesting(false)
  }

  const handleSave = async () => {
    if (!ip) return Alert.alert('Error', 'Enter server IP')
    await saveServerIp(ip)
    testConnection(ip)
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll}>
        <Text style={styles.title}>Settings</Text>

        {/* Server Connection */}
        <Card>
          <Text style={styles.label}>Server IP Address</Text>
          <Text style={styles.hint}>Your Mac's local IP (same WiFi network)</Text>

          <TextInput
            style={styles.input}
            value={ip}
            onChangeText={setIp}
            placeholder="192.168.0.104"
            placeholderTextColor={colors.text.dim}
            keyboardType="numeric"
            autoCapitalize="none"
            autoCorrect={false}
          />

          <View style={styles.btnRow}>
            <TouchableOpacity style={styles.testBtn} onPress={() => testConnection()} disabled={testing}>
              <Text style={styles.testBtnText}>{testing ? 'Testing...' : 'Test Connection'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.saveBtn} onPress={handleSave}>
              <Text style={styles.saveBtnText}>Save</Text>
            </TouchableOpacity>
          </View>

          {status === 'connected' && (
            <View style={styles.statusRow}>
              <View style={[styles.dot, { backgroundColor: colors.green[400] }]} />
              <Text style={[styles.statusText, { color: colors.green[400] }]}>Connected to server</Text>
            </View>
          )}
          {status === 'failed' && (
            <View style={styles.statusRow}>
              <View style={[styles.dot, { backgroundColor: colors.red[400] }]} />
              <Text style={[styles.statusText, { color: colors.red[400] }]}>Cannot reach server</Text>
            </View>
          )}
        </Card>

        {/* How to find IP */}
        <Card style={{ marginTop: 12 }}>
          <Text style={styles.label}>How to find your Mac's IP</Text>
          <Text style={styles.helpText}>System Settings {'\u2192'} Wi-Fi {'\u2192'} Details {'\u2192'} IP Address</Text>
          <Text style={[styles.helpText, { marginTop: 4 }]}>Or run in Terminal: ipconfig getifaddr en0</Text>
        </Card>

        {/* Current Config */}
        <Card style={{ marginTop: 12 }}>
          <Text style={styles.label}>Current API URL</Text>
          <Text style={styles.configText}>{getApiBase()}</Text>
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
  label: { fontSize: 11, fontWeight: '600', color: colors.text.secondary, marginBottom: 4 },
  hint: { fontSize: 10, color: colors.text.dim, marginBottom: 10 },
  input: {
    backgroundColor: colors.dark[800],
    borderWidth: 1,
    borderColor: colors.dark[500],
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.text.primary,
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 1,
  },
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 12 },
  testBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.blue[400] + '40',
    backgroundColor: colors.blue[400] + '15',
    alignItems: 'center',
  },
  testBtnText: { fontSize: 13, fontWeight: '700', color: colors.blue[400] },
  saveBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: colors.orange[400],
    alignItems: 'center',
  },
  saveBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 12, fontWeight: '600' },
  helpText: { fontSize: 11, color: colors.text.muted, lineHeight: 18 },
  configText: { fontSize: 12, fontFamily: 'monospace', color: colors.text.muted, marginTop: 4 },
})
