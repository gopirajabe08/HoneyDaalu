import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import BrokerConnect from './components/BrokerConnect'
import EquityPage from './components/EquityPage'
import PositionsPage from './components/PositionsPage'
import TradeLog from './components/TradeLog'
import SettingsPage from './components/SettingsPage'
import AboutPage from './components/AboutPage'
import DailyPnL from './components/DailyPnL'
import OptionsPage from './components/OptionsPage'
import FuturesPage from './components/FuturesPage'
import BTSTPage from './components/BTSTPage'
import LoginPage from './components/LoginPage'
// import ImprovementTracker from './components/ImprovementTracker'  // Disabled — auto-tune removed
import { getBrokerStatus, checkAuthStatus, logout } from './services/api'
import { getAuthToken } from './services/api/base'
import { ThemeProvider } from './contexts/ThemeContext'

function AppContent() {
  const [activePage, setActivePage] = useState('dashboard')
  const [equityCapital, setEquityCapital] = useState(75000)
  const [optionsCapital, setOptionsCapital] = useState(25000)
  const [futuresCapital, setFuturesCapital] = useState(100000)
  const [btstCapital, setBtstCapital] = useState(100000)
  const [brokerStatus, setBrokerStatus] = useState({ connected: false, configured: false })

  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)

  // Check auth on mount
  useEffect(() => {
    async function checkAuth() {
      const token = getAuthToken()
      if (!token) {
        setIsAuthenticated(false)
        setAuthChecked(true)
        return
      }

      try {
        const result = await checkAuthStatus()
        setIsAuthenticated(result.authenticated === true)
      } catch {
        setIsAuthenticated(false)
      }
      setAuthChecked(true)
    }

    checkAuth()
  }, [])

  // Listen for auth:logout events (fired by API interceptor on 401)
  useEffect(() => {
    function handleLogout() {
      setIsAuthenticated(false)
    }

    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [])

  // Scroll to top on page navigation
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [activePage])

  useEffect(() => {
    if (!isAuthenticated) return
    const fetchStatus = () =>
      getBrokerStatus()
        .then(setBrokerStatus)
        .catch(() => setBrokerStatus({ connected: false, configured: false }))
    fetchStatus()
    const iv = setInterval(fetchStatus, 30000)
    return () => clearInterval(iv)
  }, [isAuthenticated])

  function handleLoginSuccess(email) {
    setIsAuthenticated(true)
  }

  function handleLogout() {
    logout()
    setIsAuthenticated(false)
    setActivePage('dashboard')
  }

  // Show nothing while checking auth (prevents flash)
  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="animate-spin w-8 h-8 border-2 border-t-transparent rounded-full" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
      </div>
    )
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />
  }

  function renderPage() {
    switch (activePage) {
      case 'dashboard':
        return <Dashboard brokerStatus={brokerStatus} />

      case 'equity':
        return <EquityPage capital={equityCapital} setCapital={setEquityCapital} />

      case 'positions':
        return <PositionsPage brokerConnected={brokerStatus?.connected} />

      case 'logs':
        return <TradeLog />

      case 'daily-pnl':
        return <DailyPnL />

      case 'settings':
        return <SettingsPage />

      case 'about':
        return <AboutPage />

      case 'options':
        return <OptionsPage capital={optionsCapital} setCapital={setOptionsCapital} />

      case 'futures':
        return <FuturesPage capital={futuresCapital} setCapital={setFuturesCapital} />

      case 'btst':
        return <BTSTPage capital={btstCapital} setCapital={setBtstCapital} />

      default:
        return null
    }
  }

  return (
    <div className="min-h-screen theme-transition" style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      <Sidebar activePage={activePage} onNavigate={setActivePage} onLogout={handleLogout} />

      <div className="ml-[72px]">
        <Header brokerStatus={brokerStatus} />

        <main className="px-6 pb-8">
          {renderPage()}
        </main>
      </div>

      {/* ImprovementTracker disabled — auto-tune removed */}
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  )
}
