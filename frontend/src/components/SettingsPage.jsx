import React, { useState, useEffect } from 'react'
import { Settings, Shield, Clock, BarChart3, IndianRupee, Repeat, Microscope, Database, PieChart, Scale, Fingerprint, Globe, Gauge } from 'lucide-react'

export default function SettingsPage() {
  const [compliance, setCompliance] = useState(null)

  useEffect(() => {
    fetch('/api/compliance/status')
      .then(r => r.json())
      .then(setCompliance)
      .catch(() => null)
  }, [])

  const statusColor = (s) => s === 'compliant' || s === 'configured' || s === 'enforced' ? 'text-green-400' : s === 'warning' ? 'text-yellow-400' : 'text-gray-400'
  const statusDot = (s) => s === 'compliant' || s === 'configured' || s === 'enforced' ? 'bg-green-400' : s === 'warning' ? 'bg-yellow-400' : 'bg-gray-400'

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <Settings size={18} className="text-emerald-400" />
        <h2 className="text-lg font-semibold text-white">Settings</h2>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {/* SEBI Compliance */}
        <div className="col-span-4 bg-gradient-to-r from-emerald-500/5 to-cyan-500/5 rounded-2xl border border-emerald-500/20 p-5 mb-2">
          <div className="flex items-center gap-2 mb-4">
            <Scale size={16} className="text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">SEBI Algo Trading Compliance</h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium ml-auto">Effective April 1, 2026</span>
          </div>
          <div className="grid grid-cols-5 gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Fingerprint size={13} className="text-cyan-400" />
                <span className="text-[11px] text-gray-400">Strategy IDs</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${statusDot(compliance?.strategy_ids?.status)}`} />
                <span className={`text-xs font-medium ${statusColor(compliance?.strategy_ids?.status)}`}>
                  {compliance?.strategy_ids?.total_strategies || '...'} strategies tagged
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Gauge size={13} className="text-cyan-400" />
                <span className="text-[11px] text-gray-400">OPS Limit</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${statusDot(compliance?.ops_limit?.status)}`} />
                <span className={`text-xs font-medium ${statusColor(compliance?.ops_limit?.status)}`}>
                  {compliance?.ops_limit?.safety_margin || 8}/sec (SEBI: 10)
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Shield size={13} className="text-cyan-400" />
                <span className="text-[11px] text-gray-400">2FA (TOTP)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${statusDot(compliance?.two_factor_auth?.status)}`} />
                <span className={`text-xs font-medium ${statusColor(compliance?.two_factor_auth?.status)}`}>
                  Enforced
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Globe size={13} className="text-cyan-400" />
                <span className="text-[11px] text-gray-400">Static IP</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${statusDot(compliance?.static_ip?.status)}`} />
                <span className={`text-xs font-medium ${statusColor(compliance?.static_ip?.status)}`}>
                  Pending setup
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Scale size={13} className="text-cyan-400" />
                <span className="text-[11px] text-gray-400">Algo Registration</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${statusDot(compliance?.algo_registration?.status)}`} />
                <span className={`text-xs font-medium ${statusColor(compliance?.algo_registration?.status)}`}>
                  Pending
                </span>
              </div>
            </div>
          </div>
        </div>
        {/* Intraday Risk Management */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield size={16} className="text-purple-400" />
            <h3 className="text-sm font-semibold text-white">Intraday Risk Management</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Risk per trade" value="2% of capital" />
            <InfoRow label="Max open positions" value="4" />
            <InfoRow label="Position sizing" value="Based on SL distance" />
            <InfoRow label="Order type" value="Bracket Order (BO)" />
            <InfoRow label="Product type" value="INTRADAY" />
          </div>
        </div>

        {/* Intraday Schedule */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Clock size={16} className="text-green-400" />
            <h3 className="text-sm font-semibold text-white">Intraday Schedule</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Market hours" value="9:15 AM - 3:30 PM IST" />
            <InfoRow label="Scan interval" value="Every 15 minutes" />
            <InfoRow label="Order cutoff" value="2:00 PM IST" />
            <InfoRow label="Auto square-off" value="3:15 PM IST" />
          </div>
        </div>

        {/* Swing Trading */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Repeat size={16} className="text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">Swing Trading</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Max open positions" value="1" />
            <InfoRow label="Product type" value="CNC (carry-forward)" />
            <InfoRow label="Scan schedule (1d)" value="9:20 AM + 3:35 PM" />
            <InfoRow label="Scan schedule (1h)" value="Every 2 hours (auto)" />
            <InfoRow label="Position carry" value="Overnight / multi-day" />
            <InfoRow label="Exit" value="SL hit or Target hit only" />
          </div>
        </div>

        {/* Data Sources */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Database size={16} className="text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">Data Sources</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Dashboard P&L" value="TradeJini Positions (live)" />
            <InfoRow label="Dashboard Brokerage" value="TradeJini Orders + Turnover" />
            <InfoRow label="Daily P&L (today)" value="TradeJini Positions (live)" />
            <InfoRow label="Daily P&L (history)" value="Trade Logger" />
            <InfoRow label="Daily P&L modes" value="Live / Paper toggle" />
            <InfoRow label="Trade Log" value="Trade Logger (.trade_history.json)" />
          </div>
        </div>

        {/* Brokerage Calculation */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <IndianRupee size={16} className="text-yellow-400" />
            <h3 className="text-sm font-semibold text-white">Brokerage & Charges</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Brokerage" value="₹20 per executed order" />
            <InfoRow label="STT (sell)" value="0.025% of sell value" />
            <InfoRow label="Exchange txn" value="0.00297% of turnover" />
            <InfoRow label="GST" value="18% on (brokerage + exchange)" />
            <InfoRow label="SEBI charges" value="₹10 per crore turnover" />
            <InfoRow label="Stamp duty (buy)" value="0.003% of buy value" />
            <InfoRow label="Source" value="TradeJini buyVal/sellVal + filled orders" />
            <InfoRow label="Display" value="Gross P&L + Charges shown separately" />
          </div>
        </div>

        {/* Daily P&L Charts */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <PieChart size={16} className="text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">Daily P&L Page</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Charts" value="Profit vs Loss & Strategy-wise (Pie)" />
            <InfoRow label="Brokerage chart" value="Bar chart (live mode only)" />
            <InfoRow label="Live mode" value="Auto + Swing live trades" />
            <InfoRow label="Paper mode" value="Paper + Swing paper trades" />
            <InfoRow label="Today override" value="TradeJini positions (source of truth)" />
            <InfoRow label="History" value="Trade Logger (past days)" />
          </div>
        </div>

        {/* Algo Specialists */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Microscope size={16} className="text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">Algo Specialists</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Specialists" value="6 AI analysis agents" />
            <InfoRow label="Trigger" value="Single 'Generate' button" />
            <InfoRow label="Report" value="Accumulated findings + recommendations" />
            <InfoRow label="Deploy" value="One-click for deployable recommendations" />
            <InfoRow label="Persistence" value="Deployed items saved per day" />
            <InfoRow label="Re-generate" value="Deployed items stay hidden" />
          </div>
        </div>

        {/* Strategy Info */}
        <div className="col-span-4 bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={16} className="text-blue-400" />
            <h3 className="text-sm font-semibold text-white">Strategy Universe</h3>
          </div>
          <div className="grid grid-cols-3 gap-x-8 gap-y-3">
            <InfoRow label="Stock universe" value="Nifty 500" />
            <InfoRow label="Data source" value="yfinance + TradeJini" />
            <InfoRow label="Play #1 — EMA Crossover" value="Long + Short | Intraday + Swing" />
            <InfoRow label="Play #2 — Triple MA" value="Long + Short | Intraday + Swing" />
            <InfoRow label="Play #3 — VWAP Pullback" value="Long + Short | Intraday only" />
            <InfoRow label="Play #4 — Supertrend" value="Long + Short | Intraday only" />
            <InfoRow label="Play #5 — BB Squeeze" value="Long + Short | Intraday + Swing" />
            <InfoRow label="Play #6 — BB Contra" value="Long + Short | Intraday + Swing" />
            <InfoRow label="Nifty trend filter" value="Blocks counter-trend trades" />
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-gray-400">{label}</span>
      <span className="text-[11px] text-white font-medium">{value}</span>
    </div>
  )
}
