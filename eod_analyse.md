# Task: Integrate EOD Analyst Page into SmartAlgo (IntraTrading) App

## Project Location
```
/Users/vgopiraja/Documents/MY Applications/IntraTrading/frontend/src/
```

## What You Must Do
Integrate a new **EOD Strategy Analyst** page into the existing React + Vite app. The app uses:
- React with `useState` (no React Router — navigation is a `activePage` state string in `App.jsx`)
- Tailwind CSS with custom `dark-*` classes (`dark-600`, `dark-700`, `dark-800`, `dark-900`)
- Lucide React icons
- Backend API at `http://localhost:8001`
- Anthropic API at `https://api.anthropic.com/v1/messages`

Do **exactly** these 3 file operations:

---

## FILE 1 — CREATE (new file)
**Path:** `src/components/EODAnalyst.jsx`

**Full content:**
```jsx
import React, { useState, useEffect, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, AlertTriangle, RefreshCw,
  Brain, ChevronRight, BarChart2, Layers, AlertCircle, Activity
} from 'lucide-react'

const BASE = 'http://localhost:8001'

const STRATEGY_META = {
  play1_ema_crossover: { name: 'EMA-EMA Crossover',     color: 'text-yellow-400' },
  play2_triple_ma:     { name: 'Triple MA Filter',       color: 'text-purple-400' },
  play3_vwap_pullback: { name: 'VWAP Trend-Pullback',    color: 'text-blue-400'   },
  play4_supertrend:    { name: 'Supertrend Power Trend', color: 'text-green-400'  },
  play5_bb_squeeze:    { name: 'BB Squeeze Breakout',    color: 'text-red-400'    },
  play6_bb_mean_rev:   { name: 'BB Mean Reversion',      color: 'text-pink-400'   },
}

const STATUS_MAP = { 1:'PENDING', 2:'FILLED', 4:'TRANSIT', 5:'REJECTED', 6:'CANCELLED', 20:'MOD' }
const api   = async (path) => { try { return await (await fetch(`${BASE}${path}`)).json() } catch { return null } }
const inr   = (v) => `₹${Math.abs(v??0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}`
const sgn   = (v) => (v??0) >= 0 ? '+' : '-'
const clr   = (v) => (v??0) >= 0 ? 'text-green-400' : 'text-red-400'
const today = () => new Date().toLocaleDateString('en-IN',{weekday:'long',year:'numeric',month:'long',day:'numeric'})

const Card = ({ children, className='' }) => (
  <div className={`bg-dark-800 border border-dark-600 rounded-xl p-4 ${className}`}>{children}</div>
)
const KPI = ({ label, value, color, sub }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-gray-500 text-xs">{label}</span>
    <span className={`text-base font-bold ${color??'text-white'}`}>{value}</span>
    {sub && <span className="text-gray-600 text-xs">{sub}</span>}
  </div>
)
const Badge = ({ label, color }) => {
  const map = {
    green:'bg-green-900/60 text-green-300 border-green-700',
    red:'bg-red-900/60 text-red-300 border-red-700',
    yellow:'bg-yellow-900/60 text-yellow-300 border-yellow-700',
    blue:'bg-blue-900/60 text-blue-300 border-blue-700',
    orange:'bg-orange-900/60 text-orange-300 border-orange-700',
    gray:'bg-dark-600 text-gray-400 border-dark-500',
  }
  return <span className={`text-xs px-2 py-0.5 rounded border font-semibold ${map[color]??map.gray}`}>{label}</span>
}
const SectionHead = ({ icon:Icon, title }) => (
  <div className="flex items-center gap-2 mb-3">
    <Icon size={16} className="text-orange-400" />
    <h3 className="text-white font-semibold text-sm tracking-wide">{title}</h3>
  </div>
)

export default function EODAnalyst() {
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [analysing, setAnalysing] = useState(false)
  const [analysis,  setAnalysis]  = useState(null)
  const [error,     setError]     = useState(null)
  const [tab,       setTab]       = useState('overview')

  const fetchData = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [strategiesRaw, tradesRaw, ordersRaw, positionsRaw, autoRaw] = await Promise.all([
        api('/api/strategies'), api('/api/fyers/trades'), api('/api/fyers/orders'),
        api('/api/fyers/positions'), api('/api/auto/status'),
      ])
      const orders = (ordersRaw?.orderBook??[]).map(o=>({
        symbol: o.symbol?.replace('NSE:','').replace('-EQ',''),
        side: o.side===1?'BUY':'SELL', qty:o.qty, filledQty:o.filledQty,
        productType:o.productType, limitPrice:o.limitPrice, tradedPrice:o.tradedPrice,
        status:STATUS_MAP[o.status]??String(o.status), message:o.message, time:o.orderDateTime,
      }))
      const trades = (tradesRaw?.tradeBook??[]).map(t=>({
        symbol:t.symbol?.replace('NSE:','').replace('-EQ',''),
        side:t.side===1?'BUY':'SELL', qty:t.tradedQty, price:t.tradePrice,
        value:t.tradeValue, time:t.orderDateTime, productType:t.productType,
      }))
      const positions = (positionsRaw?.netPositions??[]).map(p=>({
        symbol:p.symbol?.replace('NSE:','').replace('-EQ',''),
        netQty:p.netQty, buyAvg:p.buyAvg, sellAvg:p.sellAvg,
        realizedPL:p.realized_profit??0, unrealizedPL:p.unrealized_profit??0,
        totalPL:p.pl??0, ltp:p.ltp, productType:p.productType,
      }))
      const filled    = orders.filter(o=>o.status==='FILLED')
      const rejected  = orders.filter(o=>o.status==='REJECTED')
      const pending   = orders.filter(o=>o.status==='PENDING')
      const cancelled = orders.filter(o=>o.status==='CANCELLED')
      setData({
        strategies:strategiesRaw??[], orders, trades, positions,
        filled, rejected, pending, cancelled,
        totalPL:     positions.reduce((s,p)=>s+p.totalPL,0),
        realizedPL:  positions.reduce((s,p)=>s+p.realizedPL,0),
        unrealizedPL:positions.reduce((s,p)=>s+p.unrealizedPL,0),
        activeStrategies:autoRaw?.strategies??[],
        capital:autoRaw?.capital??100000,
        scanCount:autoRaw?.scan_count??0,
        today:today(),
      })
    } catch(e) { setError('Cannot connect to SmartAlgo backend at localhost:8001') }
    setLoading(false)
  }, [])

  useEffect(()=>{ fetchData() },[fetchData])

  const runAnalysis = useCallback(async () => {
    if (!data) return
    setAnalysing(true); setAnalysis(null); setTab('analysis')
    const d = data
    const prompt = `You are an expert Algorithmic Trading Strategist for Indian equity markets.
Analyse today's SmartAlgo intraday session and give a sharp EOD report.

Date: ${d.today}
Capital: ₹${d.capital.toLocaleString('en-IN')} | Universe: Nifty 500 | Order Type: Bracket Order (BO)
Risk/trade: 2% | Max positions: 3 | Scan: every 15 min | Cutoff: 2 PM | Square-off: 3:15 PM IST

ACTIVE STRATEGIES TODAY:
${d.activeStrategies.map(s=>`• ${STRATEGY_META[s.strategy]?.name??s.strategy} (${s.timeframe})`).join('\n')||'None'}

ALL 6 STRATEGIES:
${d.strategies.map(s=>`[${s.id}] ${s.name}: ${s.description} | Indicators: ${s.indicators?.join(', ')} | Entry: ${s.long_setup} | SL: ${s.stop_loss_rules} | Exit: ${s.exit_rules}`).join('\n')}

ORDERS (${d.orders.length} total):
FILLED (${d.filled.length}): ${d.filled.map(o=>`${o.symbol} ${o.side} ${o.qty}@₹${o.tradedPrice} [${o.productType}] ${o.time}`).join(' | ')||'none'}
REJECTED (${d.rejected.length}): ${d.rejected.map(o=>`${o.symbol} — ${o.message}`).join(' | ')||'none'}
PENDING (${d.pending.length}): ${d.pending.map(o=>`${o.symbol} ${o.side} ${o.qty}@₹${o.limitPrice}`).join(' | ')||'none'}

TRADE BOOK:
${d.trades.map(t=>`${t.symbol} ${t.side} ${t.qty}@₹${t.price} [${t.productType}] ${t.time}`).join('\n')||'No trades'}

POSITIONS:
${d.positions.map(p=>`${p.symbol}: qty=${p.netQty} buyAvg=₹${p.buyAvg?.toFixed(2)} ltp=₹${p.ltp} realised=₹${p.realizedPL?.toFixed(2)} unrealised=₹${p.unrealizedPL?.toFixed(2)}`).join('\n')||'None'}
NET P&L: ₹${d.totalPL.toFixed(2)} (Realised ₹${d.realizedPL.toFixed(2)} + Unrealised ₹${d.unrealizedPL.toFixed(2)})

Use web search to get today's Nifty 50 close, India VIX level and direction, and market character.

Reply in this EXACT plain-text format — no markdown, no asterisks, no bullet symbols:

MARKET VERDICT
[One line: session type and impact on BO strategies on Nifty 500 stocks]

SCORECARD
Net P&L: [value + brief judgement]
Order fill rate: [X/Y, rejection notes if any]
Capital utilised: [% of total capital]

STRATEGY ANALYSIS
[For each active strategy: what signals fired, how trades performed, why — be specific with symbols/prices]

ISSUES FOUND TODAY
[Numbered list of actual bugs/problems from the data — specific, no generics]

RECOMMENDATIONS FOR TOMORROW
[Per strategy: keep/modify/pause + exact parameter values to change]

CONFIDENCE RATINGS
[Per strategy: HIGH / MEDIUM / LOW + one-line reason]`

    try {
      const res = await fetch('https://api.anthropic.com/v1/messages',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          model:'claude-sonnet-4-20250514', max_tokens:1000,
          tools:[{type:'web_search_20250305',name:'web_search'}],
          system:"You are a sharp algorithmic trading strategist for Indian markets. Always search for today's Nifty 50 close and India VIX before answering. Be direct and data-driven.",
          messages:[{role:'user',content:prompt}],
        }),
      })
      const json = await res.json()
      const text = (json.content??[]).filter(b=>b.type==='text').map(b=>b.text).join('\n')
      setAnalysis(text||'No analysis returned.')
    } catch(e) { setAnalysis('Analysis failed: '+e.message) }
    setAnalysing(false)
  },[data])

  const pl      = data?.totalPL??0
  const openPos = data?.positions.filter(p=>p.netQty!==0)??[]
  const tabs    = ['overview','trades','positions','analysis']

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Brain size={20} className="text-orange-400"/>
            EOD Strategy Analyst
          </h2>
          <p className="text-gray-500 text-xs mt-0.5">{data?.today??'—'} · Nifty 500</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchData} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-dark-700 hover:bg-dark-600 border border-dark-500 rounded-lg text-gray-300 text-xs transition disabled:opacity-40">
            <RefreshCw size={13} className={loading?'animate-spin':''}/>
            {loading?'Loading…':'Refresh'}
          </button>
          <button onClick={runAnalysis} disabled={!data||analysing||loading}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-gradient-to-r from-orange-500 to-pink-500 hover:from-orange-400 hover:to-pink-400 text-white rounded-lg text-xs font-semibold transition disabled:opacity-40">
            <Brain size={13}/>
            {analysing?'Analysing…':'Run EOD Analysis'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-700 rounded-xl text-red-300 text-xs">
          <AlertCircle size={14}/>{error}
        </div>
      )}

      {loading && !data && (
        <div className="grid grid-cols-6 gap-3">
          {[...Array(6)].map((_,i)=>(
            <div key={i} className="h-16 bg-dark-700 rounded-xl animate-pulse"/>
          ))}
        </div>
      )}

      {data && (<>
        {/* KPI strip */}
        <div className="grid grid-cols-6 gap-3">
          {[
            {label:'Net P&L',       value:`${sgn(pl)}${inr(pl)}`,                              color:clr(pl)},
            {label:'Unrealised',    value:`${sgn(data.unrealizedPL)}${inr(data.unrealizedPL)}`, color:clr(data.unrealizedPL)},
            {label:'Filled Orders', value:`${data.filled.length} / ${data.orders.length}`,      sub:'filled / total'},
            {label:'Rejected',      value:data.rejected.length,                                 color:data.rejected.length?'text-red-400':'text-gray-400'},
            {label:'Open Positions',value:openPos.length,                                       color:openPos.length?'text-yellow-400':'text-gray-400'},
            {label:'Scans Run',     value:data.scanCount,                                       color:'text-blue-400'},
          ].map(k=>(<Card key={k.label}><KPI {...k}/></Card>))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-dark-600">
          {tabs.map(t=>(
            <button key={t} onClick={()=>setTab(t)}
              className={`px-4 py-2 text-xs font-semibold capitalize transition rounded-t-lg
                ${tab===t?'bg-dark-700 text-orange-400 border-b-2 border-orange-400':'text-gray-500 hover:text-gray-300'}`}>
              {t==='analysis'?'🧠 AI Analysis':t.charAt(0).toUpperCase()+t.slice(1)}
            </button>
          ))}
        </div>

        {/* OVERVIEW */}
        {tab==='overview' && (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-4">
              <Card>
                <SectionHead icon={Activity} title="Strategies Running Today"/>
                <div className="space-y-2">
                  {data.activeStrategies.length===0
                    ? <p className="text-gray-500 text-xs">No auto-trading session today</p>
                    : data.activeStrategies.map(s=>{
                        const m=STRATEGY_META[s.strategy]??{name:s.strategy,color:'text-gray-400'}
                        return (
                          <div key={s.strategy} className="flex items-center justify-between py-1">
                            <div>
                              <span className={`text-sm font-semibold ${m.color}`}>{m.name}</span>
                              <span className="text-gray-500 text-xs ml-2">{s.timeframe}</span>
                            </div>
                            <Badge label="ACTIVE" color="green"/>
                          </div>
                        )
                      })
                  }
                  {data.strategies
                    .filter(s=>!data.activeStrategies.find(a=>a.strategy===s.id))
                    .map(s=>(
                      <div key={s.id} className="flex items-center justify-between py-1 opacity-40">
                        <span className="text-gray-400 text-sm">{s.name}</span>
                        <Badge label="INACTIVE" color="gray"/>
                      </div>
                    ))
                  }
                </div>
              </Card>
              <Card>
                <SectionHead icon={BarChart2} title="Order Summary"/>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    {label:'Filled',    count:data.filled.length,    color:'green'},
                    {label:'Rejected',  count:data.rejected.length,  color:data.rejected.length?'red':'gray'},
                    {label:'Pending',   count:data.pending.length,   color:data.pending.length?'yellow':'gray'},
                    {label:'Cancelled', count:data.cancelled.length, color:data.cancelled.length?'orange':'gray'},
                  ].map(o=>(
                    <div key={o.label} className="flex items-center justify-between p-2 bg-dark-700 rounded-lg">
                      <span className="text-gray-400 text-xs">{o.label}</span>
                      <Badge label={o.count} color={o.color}/>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
            <div className="space-y-4">
              <Card>
                <SectionHead icon={Layers} title="Positions & P&L"/>
                {data.positions.length===0
                  ? <p className="text-gray-500 text-xs">No positions today</p>
                  : <div className="space-y-2">
                      {data.positions.map(p=>(
                        <div key={p.symbol} className="flex items-center justify-between py-1 border-b border-dark-600 last:border-0">
                          <div>
                            <span className="text-white font-semibold text-sm">{p.symbol}</span>
                            <span className={`text-xs ml-2 ${p.netQty!==0?'text-yellow-400':'text-gray-500'}`}>
                              {p.netQty!==0?`${p.netQty} OPEN`:'CLOSED'}
                            </span>
                          </div>
                          <div className="text-right">
                            <div className={`text-sm font-bold ${clr(p.totalPL)}`}>{sgn(p.totalPL)}{inr(p.totalPL)}</div>
                            <div className="text-gray-500 text-xs">LTP ₹{p.ltp}</div>
                          </div>
                        </div>
                      ))}
                      <div className="flex justify-between pt-2">
                        <span className="text-gray-400 text-xs font-semibold">NET P&L</span>
                        <span className={`text-sm font-bold ${clr(pl)}`}>{sgn(pl)}{inr(pl)}</span>
                      </div>
                    </div>
                }
              </Card>
              {data.rejected.length>0 && (
                <Card className="border-red-900">
                  <SectionHead icon={AlertTriangle} title="Rejected Orders — Fix Required"/>
                  {data.rejected.map((o,i)=>(
                    <div key={i} className="mb-2 p-2 bg-red-900/20 rounded-lg border border-red-900">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-red-300 font-semibold text-sm">{o.symbol}</span>
                        <Badge label={o.side} color={o.side==='BUY'?'green':'red'}/>
                      </div>
                      <p className="text-red-400 text-xs">{o.message}</p>
                      <p className="text-gray-500 text-xs mt-0.5">{o.time}</p>
                    </div>
                  ))}
                </Card>
              )}
            </div>
          </div>
        )}

        {/* TRADES */}
        {tab==='trades' && (
          <Card>
            <SectionHead icon={ChevronRight} title={`Trade Book — ${data.trades.length} trades today`}/>
            {data.trades.length===0
              ? <p className="text-gray-500 text-xs text-center py-8">No trades executed today</p>
              : <div className="overflow-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-gray-500 border-b border-dark-600">
                        {['Symbol','Side','Qty','Price','Value','Product','Time'].map(h=>(
                          <th key={h} className="text-left py-2 pr-4 font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.trades.map((t,i)=>(
                        <tr key={i} className="border-b border-dark-700 hover:bg-dark-700/50 transition">
                          <td className="py-2 pr-4 font-semibold text-white">{t.symbol}</td>
                          <td className="pr-4"><Badge label={t.side} color={t.side==='BUY'?'green':'red'}/></td>
                          <td className="pr-4 text-gray-300">{t.qty}</td>
                          <td className="pr-4 text-gray-300">₹{t.price}</td>
                          <td className="pr-4 text-gray-400">₹{t.value?.toLocaleString('en-IN',{maximumFractionDigits:0})}</td>
                          <td className="pr-4"><Badge label={t.productType} color="blue"/></td>
                          <td className="text-gray-500">{t.time?.split(' ')[1]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
            }
          </Card>
        )}

        {/* POSITIONS */}
        {tab==='positions' && (
          <div className="space-y-3">
            {data.positions.length===0
              ? <Card><p className="text-gray-500 text-xs text-center py-8">No positions today</p></Card>
              : data.positions.map(p=>(
                  <Card key={p.symbol} className="grid grid-cols-7 gap-4 items-center">
                    <div className="col-span-2">
                      <div className="text-white font-bold">{p.symbol}</div>
                      <div className="text-gray-500 text-xs">{p.productType}</div>
                    </div>
                    <KPI label="Net Qty"    value={p.netQty}                          color={p.netQty>0?'text-green-400':p.netQty<0?'text-red-400':'text-gray-400'}/>
                    <KPI label="Buy Avg"    value={`₹${p.buyAvg?.toFixed(2)}`}/>
                    <KPI label="LTP"        value={`₹${p.ltp}`}/>
                    <KPI label="Realised"   value={`${sgn(p.realizedPL)}${inr(p.realizedPL)}`}   color={clr(p.realizedPL)}/>
                    <KPI label="Unrealised" value={`${sgn(p.unrealizedPL)}${inr(p.unrealizedPL)}`} color={clr(p.unrealizedPL)}/>
                  </Card>
                ))
            }
            <Card className="flex justify-between items-center bg-dark-700">
              <span className="text-gray-300 font-semibold text-sm">NET P&L (Realised + Unrealised)</span>
              <span className={`text-xl font-bold ${clr(pl)}`}>{sgn(pl)}{inr(pl)}</span>
            </Card>
          </div>
        )}

        {/* AI ANALYSIS */}
        {tab==='analysis' && (
          <div className="space-y-4">
            {!analysis && !analysing && (
              <Card className="text-center py-16">
                <Brain size={40} className="text-orange-400 mx-auto mb-4"/>
                <p className="text-white font-semibold mb-1">AI-Powered EOD Analysis</p>
                <p className="text-gray-500 text-xs mb-6 max-w-sm mx-auto">
                  Fetches live Nifty/VIX data, analyses every trade vs today's market conditions,
                  flags execution bugs, and gives specific parameter changes for tomorrow.
                </p>
                <button onClick={runAnalysis}
                  className="inline-flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-pink-500 hover:from-orange-400 hover:to-pink-400 text-white rounded-xl font-semibold text-sm transition">
                  <Brain size={16}/> Run EOD Analysis
                </button>
              </Card>
            )}
            {analysing && (
              <Card className="text-center py-16">
                <RefreshCw size={32} className="text-orange-400 mx-auto mb-4 animate-spin"/>
                <p className="text-white font-semibold">Analysing today's session…</p>
                <p className="text-gray-500 text-xs mt-2">Fetching live market data + reviewing all trades</p>
              </Card>
            )}
            {analysis && (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Brain size={16} className="text-orange-400"/>
                    <span className="text-white font-semibold text-sm">EOD Analysis Report</span>
                    <span className="text-gray-500 text-xs">{data.today}</span>
                  </div>
                  <button onClick={runAnalysis} disabled={analysing}
                    className="flex items-center gap-1 px-3 py-1 bg-dark-700 hover:bg-dark-600 border border-dark-500 rounded-lg text-gray-400 text-xs transition">
                    <RefreshCw size={11}/> Re-run
                  </button>
                </div>
                <Card className="whitespace-pre-wrap leading-relaxed text-gray-200 text-xs font-mono">
                  {analysis}
                </Card>
              </>
            )}
          </div>
        )}
      </>)}
    </div>
  )
}
```

---

## FILE 2 — EDIT `src/App.jsx`

Make exactly 2 targeted changes:

**Change A** — Add this import line after the existing `BacktestPage` import:
```jsx
import EODAnalyst from './components/EODAnalyst'
```

**Change B** — Add this case inside the `renderPage()` switch statement, after the `case 'settings':` block and before `default:`:
```jsx
case 'eod':
  return <EODAnalyst />
```

---

## FILE 3 — EDIT `src/components/Sidebar.jsx`

Make exactly 2 targeted changes:

**Change A** — In the existing lucide-react import, add `Brain` to the destructured list:
```jsx
// Find this line:
import { LayoutDashboard, Crosshair, FlaskConical, Briefcase, ScrollText, Settings, LogOut } from 'lucide-react'

// Replace with:
import { LayoutDashboard, Crosshair, FlaskConical, Briefcase, ScrollText, Settings, LogOut, Brain } from 'lucide-react'
```

**Change B** — In the `navItems` array, add this as the last entry before the closing `]`:
```jsx
{ icon: Brain, label: 'EOD Analyst', page: 'eod' },
```

---

## Verification Steps

After making all changes:

1. Confirm `src/components/EODAnalyst.jsx` exists and has content
2. Confirm `src/App.jsx` contains `import EODAnalyst` and `case 'eod':`
3. Confirm `src/components/Sidebar.jsx` contains `Brain` in the import and `page: 'eod'` in `navItems`
4. Run `cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading/frontend" && npm run dev` if not already running
5. Check browser at `http://localhost:3000` — a Brain icon should appear at the bottom of the left sidebar
6. Click the Brain icon → the EOD Analyst page should load showing KPIs, tabs, and the "Run EOD Analysis" button

## Important Notes

- Do NOT use React Router — navigation is handled purely via `activePage` state in `App.jsx`
- Do NOT modify any other files
- The `dark-*` Tailwind classes (`dark-600`, `dark-700`, `dark-800`, `dark-900`) are custom classes already defined in the project — use them as-is
- The Anthropic API call in EODAnalyst.jsx does NOT need an API key in the headers — it is handled by the Claude environment
- Keep all existing app functionality exactly as-is
