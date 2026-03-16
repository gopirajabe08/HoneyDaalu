import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { colors } from '../../theme/colors'

export default function MetricCard({ label, value, valueColor, sub }) {
  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, { color: valueColor || colors.text.primary }]}>{value}</Text>
      {sub && <Text style={styles.sub}>{sub}</Text>}
    </View>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.dark[700],
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.dark[500],
    padding: 12,
    minWidth: 120,
    marginRight: 8,
  },
  label: { fontSize: 10, color: colors.text.muted, marginBottom: 4 },
  value: { fontSize: 18, fontWeight: '700' },
  sub: { fontSize: 10, color: colors.text.dim, marginTop: 2 },
})
