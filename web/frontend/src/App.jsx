import { useState, useEffect, useCallback, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import axios from 'axios'

const API = '/api'

export default function App() {
  const [watchlist, setWatchlist] = useState([])
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [strategy, setStrategy] = useState('macross')
  const [freq, setFreq] = useState('daily')
  const [loading, setLoading] = useState(false)
  const [klineData, setKlineData] = useState([])
  const [returnsCurve, setReturnsCurve] = useState([])
  const [bhBenchmark, setBhBenchmark] = useState([])
  const [signals, setSignals] = useState([])
  const [positionMap, setPositionMap] = useState({})
  const [completedTrades, setCompletedTrades] = useState([])
  const [stats, setStats] = useState(null)
  const [newSymbol, setNewSymbol] = useState('')
  const [strategies, setStrategies] = useState([])
  const abortRef = useRef(null)
  const reqSeq = useRef(0) // sequence counter to discard stale responses

  // Load watchlist
  const loadWatchlist = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/watchlist`)
      setWatchlist(res.data)
      if (res.data.length > 0 && !selectedSymbol) {
        setSelectedSymbol(res.data[0].symbol)
      }
    } catch {}
  }, [selectedSymbol])

  // Load strategies
  useEffect(() => {
    axios.get(`${API}/strategies`).then(r => setStrategies(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    loadWatchlist()
  }, [loadWatchlist])

  // Run backtest
  const runBacktest = useCallback(async () => {
    if (!selectedSymbol) return

    // Increment sequence to invalidate previous in-flight request
    const seq = ++reqSeq.current

    setLoading(true)
    try {
      const res = await axios.get(`${API}/analyze`, {
        params: { symbol: selectedSymbol, freq, strategy },
      })
      // Discard stale response if a newer request was triggered
      if (seq !== reqSeq.current) return

      setKlineData(res.data.kline || [])
      setReturnsCurve(res.data.returns_curve || [])
      setBhBenchmark(res.data.bh_benchmark || [])
      setSignals(res.data.signals || [])
      setPositionMap(res.data.position_map || {})
      setCompletedTrades(res.data.completed_trades || [])
      const trades = res.data.completed_trades || []
      const wins = trades.filter(t => t.is_profitable)
      const losses = trades.filter(t => !t.is_profitable)
      const winRate = trades.length > 0 ? (wins.length / trades.length * 100) : 0
      const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0
      const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.pnl, 0) / losses.length) : 1
      const plRatio = avgLoss > 0 ? (avgWin / avgLoss) : 0
      // Per-trade return %: (sell - buy) / buy * 100
      const avgPositiveReturn = wins.length > 0 ? wins.reduce((s, t) => s + ((t.sell_price - t.buy_price) / t.buy_price * 100), 0) / wins.length : 0
      const avgNegativeReturn = losses.length > 0 ? losses.reduce((s, t) => s + ((t.sell_price - t.buy_price) / t.buy_price * 100), 0) / losses.length : 0

      setStats({
        finalValue: res.data.final_value,
        totalReturn: res.data.total_return_pct,
        bars: res.data.bars,
        trades: trades.length,
        winCount: wins.length,
        lossCount: losses.length,
        winRate,
        plRatio,
        avgPositiveReturn,
        avgNegativeReturn,
      })
    } catch (e) {
      if (seq !== reqSeq.current) return // skip stale error
      if (e.name === 'CanceledError') return // ignore aborted requests
      console.error('Backtest failed:', e)
      setKlineData([])
      setReturnsCurve([])
      setBhBenchmark([])
      setSignals([])
      setCompletedTrades([])
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [selectedSymbol, freq, strategy])

  // Auto-run when symbol/strategy/freq changes
  useEffect(() => {
    runBacktest()
  }, [runBacktest])

  // Add symbol
  const addSymbol = async () => {
    if (!newSymbol.trim()) return
    try {
      await axios.post(`${API}/watchlist`, { symbol: newSymbol.trim(), name: '', market: '' })
      setNewSymbol('')
      await loadWatchlist()
    } catch {}
  }

  // Remove symbol
  const removeSymbol = async (symbol) => {
    try {
      await axios.delete(`${API}/watchlist/${symbol}`)
      if (selectedSymbol === symbol) setSelectedSymbol(null)
      await loadWatchlist()
    } catch {}
  }

  // --- K-line chart ---
  const klineOption = createKlineOption(klineData, completedTrades)

  // --- Returns chart ---
  const returnsOption = createReturnsOption(returnsCurve, bhBenchmark, completedTrades, klineData.map(d => d.date))

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">QuantInvest</div>

        <div className="sidebar-section">
          <h3>自选股</h3>
        </div>

        <div className="watchlist">
          {watchlist.map(item => (
            <div
              key={item.symbol}
              className={`watchlist-item ${selectedSymbol === item.symbol ? 'active' : ''}`}
              onClick={() => setSelectedSymbol(item.symbol)}
            >
              <div>
                <div className="watchlist-symbol">{item.symbol}</div>
                {item.name && <div className="watchlist-name">{item.name}</div>}
              </div>
              <button
                className="watchlist-remove"
                onClick={(e) => { e.stopPropagation(); removeSymbol(item.symbol) }}
              >×</button>
            </div>
          ))}
        </div>

        <form className="add-form" onSubmit={e => { e.preventDefault(); addSymbol() }}>
          <input
            value={newSymbol}
            onChange={e => setNewSymbol(e.target.value)}
            placeholder="输入代码 如 600519.SH"
          />
          <button type="submit">+</button>
        </form>

        <div className="strategy-selector">
          <div className="sidebar-section" style={{ padding: 0 }}>
            <h3>策略</h3>
            <select value={strategy} onChange={e => setStrategy(e.target.value)}>
              {strategies.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="freq-selector">
          <div className="sidebar-section" style={{ padding: 0 }}>
            <h3>级别</h3>
            <div className="freq-group">
              {['daily', 'weekly', '60min', '30min'].map(f => (
                <button
                  key={f}
                  className={`freq-btn ${freq === f ? 'active' : ''}`}
                  onClick={() => setFreq(f)}
                >{f}</button>
              ))}
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="main">
        <header className="main-header">
          <h2>{selectedSymbol || '选择股票'}</h2>
          <button className="run-btn" onClick={runBacktest} disabled={loading}>
            {loading ? <>Loading...</> : '运行回测'}
          </button>
        </header>

        {stats && (
          <div className="stats-row">
            <div className="stat-card multi-col">
              <div className="stat-col">
                <div className="label">总收益率</div>
                <div className={`value ${stats.totalReturn >= 0 ? 'positive' : 'negative'}`}>
                  {stats.totalReturn >= 0 ? '+' : ''}{stats.totalReturn}%
                </div>
              </div>
              <div className="stat-col">
                <div className="label">均盈</div>
                <div className="value positive">+{stats.avgPositiveReturn.toFixed(2)}%</div>
              </div>
              <div className="stat-col">
                <div className="label">均亏</div>
                <div className="value negative">{stats.avgNegativeReturn.toFixed(2)}%</div>
              </div>
            </div>
            <div className="stat-card multi-col">
              <div className="stat-col">
                <div className="label">交易次数</div>
                <div className="value">{stats.trades}</div>
              </div>
              <div className="stat-col">
                <div className="label">盈利</div>
                <div className="value positive">{stats.winCount}</div>
              </div>
              <div className="stat-col">
                <div className="label">亏损</div>
                <div className="value negative">{stats.lossCount}</div>
              </div>
            </div>
            <div className="stat-card multi-col">
              <div className="stat-col">
                <div className="label">胜率</div>
                <div className={`value ${stats.winRate >= 50 ? 'positive' : 'negative'}`}>
                  {stats.winRate.toFixed(1)}%
                </div>
              </div>
              <div className="stat-col">
                <div className="label">盈亏比</div>
                <div className={`value ${stats.plRatio >= 1 ? 'positive' : 'negative'}`}>
                  {stats.plRatio.toFixed(2)}
                </div>
              </div>
              <div className="stat-col">
                <div className="label">K线数</div>
                <div className="value">{stats.bars}</div>
              </div>
            </div>
          </div>
        )}

        <div className="charts-area">
          {klineData.length > 0 ? (
            <>
              <div className="chart-panel kline">
                <ReactECharts key={`k-${selectedSymbol}-${strategy}-${freq}`} option={klineOption} style={{ height: '100%', width: '100%' }}
                  opts={{ renderer: 'canvas' }} />
              </div>
              <div className="chart-panel equity">
                <ReactECharts key={`r-${selectedSymbol}-${strategy}-${freq}`} option={returnsOption} style={{ height: '100%', width: '100%' }}
                  opts={{ renderer: 'canvas' }} />
              </div>
            </>
          ) : (
            <div className="placeholder">
              {loading ? <><span className="loading-spinner" /> 正在加载数据...</> : '选择股票开始回测'}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}


/* ===== ECharts option builders ===== */

function createKlineOption(kline, completedTrades) {
  const dates = kline.map(d => d.date)
  const ohlc = kline.map(d => [d.open, d.close, d.low, d.high])
  const volumes = kline.map(d => d.volume)

  // Build markArea: each trade is [start, end] pair with color
  // Profit trade: red rgba(239,83,80,0.15); Loss trade: green rgba(38,166,154,0.15)
  const markAreaData = completedTrades.map(t => {
    const color = t.is_profitable ? 'rgba(239,83,80,0.15)' : 'rgba(38,166,154,0.15)'
    return [
      { name: '', xAxis: t.buy_date, itemStyle: { color } },
      { xAxis: t.sell_date },
    ]
  })

  return {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(17,24,39,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#f3f4f6', fontSize: 12 },
    },
    legend: { data: ['K线', '成交量'], textStyle: { color: '#9ca3af' }, top: 0 },
    grid: [
      { left: 60, right: 20, top: 30, height: '50%' },
      { left: 60, right: 20, top: '68%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: dates, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { show: false } },
      { type: 'category', data: dates, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { show: false }, gridIndex: 1 },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.01)', 'transparent'] } },
        axisLine: { lineStyle: { color: '#374151' } },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } },
        axisLabel: { color: '#9ca3af', fontSize: 10 },
      },
      {
        scale: true,
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#374151' } },
        splitLine: { show: false },
        axisLabel: { show: false },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 4, height: 16, borderColor: 'transparent', backgroundColor: 'rgba(255,255,255,0.03)', fillerColor: 'rgba(59,130,246,0.15)', handleStyle: { color: '#3b82f6' }, textStyle: { color: '#9ca3af', fontSize: 10 } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        barMaxWidth: 30,
        barMinWidth: 2,
        itemStyle: {
          color: '#10b981',
          color0: '#ef4444',
          borderColor: '#10b981',
          borderColor0: '#ef4444',
        },
        markArea: {
          silent: true,
          itemStyle: { borderWidth: 0 },
          data: markAreaData,
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: kline[i].close >= kline[i].open ? 'rgba(16,185,129,0.5)' : 'rgba(239,68,68,0.5)' },
        })),
      },
    ],
  }
}


function createReturnsOption(returns, benchmark, completedTrades, klineDates) {
  // Use kline dates as x-axis so markArea aligns with K-line chart
  const dates = klineDates || returns.map(d => d.date)

  // Build lookup maps from returns/benchmark data
  const retMap = {}
  for (const r of returns) retMap[r.date] = r.value
  const bhMap = {}
  for (const b of benchmark) bhMap[b.date] = b.value

  // Interpolate values onto kline dates — carry forward last known value
  let lastRet = null
  let lastBh = null
  const strategyValues = dates.map(d => { retMap[d] !== undefined && (lastRet = retMap[d]); return lastRet })
  const bhValues = dates.map(d => { bhMap[d] !== undefined && (lastBh = bhMap[d]); return lastBh })

  // Build markArea from trades
  const markAreaData = completedTrades.map(t => {
    const color = t.is_profitable ? 'rgba(239,83,80,0.15)' : 'rgba(38,166,154,0.15)'
    return [
      { name: '', xAxis: t.buy_date, itemStyle: { color } },
      { xAxis: t.sell_date },
    ]
  })

  return {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,24,39,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#f3f4f6', fontSize: 12 },
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        let tip = `<div style="margin-bottom:4px">${params[0].axisValue}</div>`
        for (const p of params) {
          const sign = p.value >= 0 ? '+' : ''
          tip += `<span style="display:inline-block;margin-right:8px;color:${p.color}">${p.seriesName}: ${sign}${p.value.toFixed(2)}%</span>`
        }
        return tip
      },
    },
    legend: {
      data: ['策略收益率', '持有基准'],
      textStyle: { color: '#9ca3af' },
      top: 0,
    },
    grid: { left: 60, right: 20, top: 30, bottom: 5 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 10,
        formatter: (v) => `${v >= 0 ? '+' : ''}${v}%`,
      },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
    ],
    series: [
      {
        name: '策略收益率',
        type: 'line',
        data: strategyValues,
        smooth: 0.3,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.08)' },
              { offset: 1, color: 'rgba(59,130,246,0.01)' },
            ],
          },
        },
        markArea: {
          silent: true,
          itemStyle: { borderWidth: 0 },
          data: markAreaData,
        },
      },
      {
        name: '持有基准',
        type: 'line',
        data: bhValues,
        smooth: 0.3,
        symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' },
      },
    ],
  }
}
