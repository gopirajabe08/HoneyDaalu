import React from 'react'
import { Settings, Shield, Clock, BarChart3, IndianRupee, Repeat, Microscope, Database, PieChart } from 'lucide-react'

export default function SettingsPage() {
  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <Settings size={18} className="text-orange-400" />
        <h2 className="text-lg font-semibold text-white">Settings</h2>
      </div>

      <div className="grid grid-cols-4 gap-4">
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
            <InfoRow label="Dashboard P&L" value="Fyers Positions (live)" />
            <InfoRow label="Dashboard Brokerage" value="Fyers Orders + Turnover" />
            <InfoRow label="Daily P&L (today)" value="Fyers Positions (live)" />
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
            <InfoRow label="Source" value="Fyers buyVal/sellVal + filled orders" />
            <InfoRow label="Display" value="Gross P&L + Charges shown separately" />
          </div>
        </div>

        {/* Daily P&L Charts */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <PieChart size={16} className="text-pink-400" />
            <h3 className="text-sm font-semibold text-white">Daily P&L Page</h3>
          </div>
          <div className="space-y-3">
            <InfoRow label="Charts" value="Profit vs Loss & Strategy-wise (Pie)" />
            <InfoRow label="Brokerage chart" value="Bar chart (live mode only)" />
            <InfoRow label="Live mode" value="Auto + Swing live trades" />
            <InfoRow label="Paper mode" value="Paper + Swing paper trades" />
            <InfoRow label="Today override" value="Fyers positions (source of truth)" />
            <InfoRow label="History" value="Trade Logger (past days)" />
          </div>
        </div>

        {/* Algo Specialists */}
        <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Microscope size={16} className="text-orange-400" />
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
            <InfoRow label="Data source" value="yfinance + Fyers" />
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
