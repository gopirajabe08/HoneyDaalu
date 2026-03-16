import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { colors } from '../../theme/colors'

export default function Badge({ label, color = colors.blue[400], small }) {
  return (
    <View style={[styles.badge, { backgroundColor: color + '20', borderColor: color + '40' }]}>
      <Text style={[styles.text, { color }, small && { fontSize: 8 }]}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  text: { fontSize: 10, fontWeight: '600' },
})
