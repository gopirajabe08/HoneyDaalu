import { useState, useEffect } from 'react'
import { Stack } from 'expo-router'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { View, Text, TouchableOpacity, StyleSheet, AppState } from 'react-native'
import * as LocalAuthentication from 'expo-local-authentication'
import { colors } from '../src/theme/colors'

function LockScreen({ onUnlock }) {
  const [error, setError] = useState('')

  const authenticate = async () => {
    setError('')
    try {
      const hasHardware = await LocalAuthentication.hasHardwareAsync()
      if (!hasHardware) {
        onUnlock() // No biometric hardware — skip lock
        return
      }

      const isEnrolled = await LocalAuthentication.isEnrolledAsync()
      if (!isEnrolled) {
        onUnlock() // No fingerprint/PIN set up — skip lock
        return
      }

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Unlock SmartAlgo',
        fallbackLabel: 'Use PIN',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
      })

      if (result.success) {
        onUnlock()
      } else {
        setError('Authentication failed. Try again.')
      }
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { authenticate() }, [])

  return (
    <View style={styles.lockContainer}>
      <View style={styles.logoBox}>
        <Text style={styles.logoText}>IT</Text>
      </View>
      <Text style={styles.appName}>SmartAlgo</Text>
      <Text style={styles.lockSubtext}>Authenticate to access trading</Text>

      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <TouchableOpacity style={styles.unlockBtn} onPress={authenticate}>
        <Text style={styles.unlockBtnText}>Unlock with Fingerprint / PIN</Text>
      </TouchableOpacity>
    </View>
  )
}

export default function RootLayout() {
  const [isLocked, setIsLocked] = useState(true)

  // Re-lock when app comes back from background
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'background') {
        setIsLocked(true)
      }
    })
    return () => sub?.remove()
  }, [])

  if (isLocked) {
    return (
      <SafeAreaProvider>
        <View style={{ flex: 1, backgroundColor: colors.dark[900] }}>
          <StatusBar style="light" backgroundColor={colors.dark[900]} />
          <LockScreen onUnlock={() => setIsLocked(false)} />
        </View>
      </SafeAreaProvider>
    )
  }

  return (
    <SafeAreaProvider>
      <View style={{ flex: 1, backgroundColor: colors.dark[900] }}>
        <StatusBar style="light" backgroundColor={colors.dark[900]} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.dark[900] } }} />
      </View>
    </SafeAreaProvider>
  )
}

const styles = StyleSheet.create({
  lockContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.dark[900],
    padding: 40,
  },
  logoBox: {
    width: 80,
    height: 80,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    backgroundColor: colors.orange[400],
  },
  logoText: {
    color: 'white',
    fontSize: 32,
    fontWeight: '800',
  },
  appName: {
    color: 'white',
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 8,
  },
  lockSubtext: {
    color: colors.text.muted,
    fontSize: 13,
    marginBottom: 30,
  },
  errorText: {
    color: colors.red[400],
    fontSize: 12,
    marginBottom: 16,
  },
  unlockBtn: {
    backgroundColor: colors.orange[400] + '20',
    borderWidth: 1,
    borderColor: colors.orange[400] + '40',
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 14,
  },
  unlockBtnText: {
    color: colors.orange[400],
    fontSize: 14,
    fontWeight: '600',
  },
})
