import { useEffect } from 'react'
import { Platform } from 'react-native'
import { Tabs } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { LayoutDashboard, Briefcase, TrendingUp, TrendingDown, BarChart3, ScrollText, Settings } from 'lucide-react-native'
import { colors } from '../../src/theme/colors'
import { loadSavedIp } from '../../src/services/api'

export default function TabLayout() {
  // Load saved server IP on app startup
  useEffect(() => { loadSavedIp() }, [])

  const insets = useSafeAreaInsets()
  const bottomPad = Platform.OS === 'android' ? Math.max(insets.bottom, 10) : 8

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.dark[800],
          borderTopColor: colors.dark[600],
          borderTopWidth: 1,
          height: 60 + bottomPad,
          paddingBottom: bottomPad,
          paddingTop: 6,
        },
        tabBarActiveTintColor: colors.orange[400],
        tabBarInactiveTintColor: colors.text.muted,
        tabBarLabelStyle: { fontSize: 10, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ color, size }) => <LayoutDashboard size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="equity"
        options={{
          title: 'Equity',
          tabBarIcon: ({ color, size }) => <Briefcase size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="options"
        options={{
          title: 'Options',
          tabBarIcon: ({ color, size }) => <TrendingUp size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="futures"
        options={{
          title: 'Futures',
          tabBarIcon: ({ color, size }) => <TrendingDown size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="daily-pnl"
        options={{
          title: 'Daily P&L',
          tabBarIcon: ({ color, size }) => <BarChart3 size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="trade-log"
        options={{
          title: 'Trades',
          tabBarIcon: ({ color, size }) => <ScrollText size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, size }) => <Settings size={size} color={color} />,
        }}
      />
    </Tabs>
  )
}
