import React from 'react'
import { IndianRupee } from 'lucide-react'

const presets = [50000, 100000, 200000, 500000, 1000000]

function formatINR(val) {
  if (val >= 100000) return `${(val / 100000).toFixed(val % 100000 === 0 ? 0 : 1)}L`
  if (val >= 1000) return `${(val / 1000).toFixed(0)}K`
  return val.toString()
}

export default function CapitalInput({ capital, setCapital }) {
  return (
    <div className="bg-dark-700 rounded-2xl border border-dark-500 p-5">
      <div className="flex items-center gap-2 mb-3">
        <IndianRupee size={18} className="text-orange-400" />
        <h3 className="text-sm font-semibold text-white">Trading Capital</h3>
      </div>

      <div className="relative mb-3">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">₹</span>
        <input
          type="number"
          value={capital}
          onChange={(e) => setCapital(Number(e.target.value) || 0)}
          className="w-full bg-dark-800 border border-dark-500 rounded-xl pl-8 pr-4 py-2.5 text-white text-sm focus:outline-none focus:border-orange-500/50 transition-colors"
          placeholder="Enter capital amount"
          min={1000}
          step={1000}
        />
      </div>

      <div className="flex gap-2 flex-wrap">
        {presets.map((val) => (
          <button
            key={val}
            onClick={() => setCapital(val)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all
              ${capital === val
                ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                : 'bg-dark-600 text-gray-400 border border-dark-500 hover:text-gray-300 hover:border-dark-400'
              }`}
          >
            ₹{formatINR(val)}
          </button>
        ))}
      </div>
    </div>
  )
}
