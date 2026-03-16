import { Stack } from 'expo-router'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { View } from 'react-native'
import { colors } from '../src/theme/colors'

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <View style={{ flex: 1, backgroundColor: colors.dark[900] }}>
        <StatusBar style="light" backgroundColor={colors.dark[900]} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.dark[900] } }} />
      </View>
    </SafeAreaProvider>
  )
}
