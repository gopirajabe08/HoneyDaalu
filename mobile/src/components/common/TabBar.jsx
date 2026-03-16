import React from 'react'
import { View, TouchableOpacity, Text, StyleSheet } from 'react-native'
import { colors } from '../../theme/colors'

export default function TabBar({ tabs, active, onSelect }) {
  return (
    <View style={styles.container}>
      {tabs.map(tab => (
        <TouchableOpacity
          key={tab.id}
          onPress={() => onSelect(tab.id)}
          style={[styles.tab, active === tab.id && { backgroundColor: (tab.activeColor || colors.orange[500]) + '20' }]}
          activeOpacity={0.7}
        >
          <Text style={[styles.text, active === tab.id && { color: tab.activeColor || colors.orange[400] }]}>
            {tab.label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: colors.dark[700],
    borderRadius: 12,
    padding: 3,
    borderWidth: 1,
    borderColor: colors.dark[500],
  },
  tab: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 10,
    alignItems: 'center',
  },
  text: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.text.muted,
  },
})
