import React from 'react'
import { TouchableOpacity, Text, StyleSheet, ActivityIndicator } from 'react-native'
import { colors } from '../../theme/colors'

export default function Button({ title, onPress, color = colors.orange[500], loading, disabled, outline, style }) {
  const bg = outline ? 'transparent' : color
  const textColor = outline ? color : '#fff'
  const borderColor = outline ? color + '50' : color

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      style={[styles.btn, { backgroundColor: bg, borderColor, opacity: disabled ? 0.5 : 1 }, style]}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator size="small" color={textColor} />
      ) : (
        <Text style={[styles.text, { color: textColor }]}>{title}</Text>
      )}
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  btn: {
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { fontSize: 14, fontWeight: '700' },
})
