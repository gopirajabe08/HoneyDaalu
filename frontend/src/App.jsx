import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import FyersConnect from './components/FyersConnect'
import EquityPage from './components/EquityPage'
import PositionsPage from './components/PositionsPage'
import TradeLog from './components/TradeLog'
import SettingsPage from './components/SettingsPage'
import AboutPage from './components/AboutPage'
import DailyPnL from './components/DailyPnL'
import OptionsPage from './components/OptionsPage'
import FuturesPage from './components/FuturesPage'
import BTSTPage from './components/BTSTPage'
// import ImprovementTracker from './components/ImprovementTracker'  // Disabled — auto-tune removed
import { getFyersStatus } from './services/api'

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')
  const [equityCapital, setEquityCapital] = useState(75000)
  const [optionsCapital, setOptionsCapital] = useState(25000)
  const [futuresCapital, setFuturesCapital] = useState(100000)
  const [btstCapital, setBtstCapital] = useState(100000)
  const [fyersStatus, setFyersStatus] = useState({ connected: false, configured: false })

  // Scroll to top on page navigation
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [activePage])

  useEffect(() => {
    getFyersStatus().then(setFyersStatus).catch(() => {})
  }, [])

  function renderPage() {
    switch (activePage) {
      case 'dashboard':
        return <Dashboard fyersStatus={fyersStatus} />

      case 'equity':
        return <EquityPage capital={equityCapital} setCapital={setEquityCapital} />

      case 'positions':
        return <PositionsPage fyersConnected={fyersStatus?.connected} />

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
    <div className="min-h-screen bg-dark-900 text-white">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />

      <div className="ml-[72px]">
        <Header fyersStatus={fyersStatus} />

        <main className="px-6 pb-8">
          {renderPage()}
        </main>
      </div>

      {/* ImprovementTracker disabled — auto-tune removed */}
    </div>
  )
}
