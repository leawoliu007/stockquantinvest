import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import axios from 'axios'

const API = '/api'

export default function App() {
  const [activeTab, setActiveTab] = useState('backtest') // 'backtest' | 'report' | 'optimizer'
  const [watchlist, setWatchlist] = useState([])
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [freq, setFreq] = useState('daily')
  const [loading, setLoading] = useState(false)     // loading cached data from DB
  const [running, setRunning] = useState(false)      // running backtest (fetching + computing)
  const [klineData, setKlineData] = useState([])
  const [returnsCurve, setReturnsCurve] = useState([])
  const [bhBenchmark, setBhBenchmark] = useState([])
  const [signals, setSignals] = useState([])
  const [positionMap, setPositionMap] = useState({})
  const [completedTrades, setCompletedTrades] = useState([])
  const [stats, setStats] = useState(null)
  const [newSymbol, setNewSymbol] = useState('')
  const [strategies, setStrategies] = useState([])
  const [resolvedSymbol, setResolvedSymbol] = useState(null)
  const [resolvedName, setResolvedName] = useState(null)
  const [resolving, setResolving] = useState(false)
  const [resolveError, setResolveError] = useState(null)
  const [ambiguousModal, setAmbiguousModal] = useState(null) // { code, alternatives, name }
  const [quotes, setQuotes] = useState({})
  const [updatingDb, setUpdatingDb] = useState(false)
  const [updateResult, setUpdateResult] = useState(null)
  // Strategy params modal state
  const [paramsSchema, setParamsSchema] = useState({})
  const [paramsModal, setParamsModal] = useState(null) // { symbol, strategy }
  const [editingParams, setEditingParams] = useState({})
  // Batch report state
  const [reportData, setReportData] = useState(null)
  const [reportRunning, setReportRunning] = useState(false)
  // Optimizer state
  const [optStrategy, setOptStrategy] = useState('macross')
  const [optSymbol, setOptSymbol] = useState('')
  const [optParamRanges, setOptParamRanges] = useState({})
  const [optResults, setOptResults] = useState(null)
  const [optRunning, setOptRunning] = useState(false)
  const resolveTimer = useRef(null)
  const abortRef = useRef(null)
  const reqSeq = useRef(0) // sequence counter to discard stale responses
  const debounceTimer = useRef(null) // debounce timer for cache loading
  const lastLoadKey = useRef(null)   // track last loaded "symbol:freq:strategy" to skip redundant loads

  // Load watchlist
  const loadWatchlist = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/watchlist`)
      setWatchlist(res.data)
      if (res.data.length > 0 && !selectedSymbol) {
        setSelectedSymbol(res.data[0].symbol)
      }
      // Fetch quotes for all watchlist symbols
      if (res.data.length > 0) {
        const symbols = res.data.map(i => i.symbol).join(",")
        axios.get(`${API}/quote`, { params: { symbols } }).then(r => {
          const quoteMap = {}
          for (const q of r.data) quoteMap[q.symbol] = q
          setQuotes(quoteMap)
        }).catch(() => {})
      }
    } catch {}
  }, [selectedSymbol])

  // Load strategies
  useEffect(() => {
    axios.get(`${API}/strategies`).then(r => setStrategies(r.data)).catch(() => {})
    axios.get(`${API}/strategy-params-schema`).then(r => setParamsSchema(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    loadWatchlist()
  }, [loadWatchlist])

  // Get strategy for selected symbol from watchlist data
  const getSelectedStrategy = () => {
    const item = watchlist.find(w => w.symbol === selectedSymbol)
    return item?.strategy || 'macross'
  }

  // Change strategy for a specific symbol
  const changeStrategy = async (symbol, newStrategy) => {
    try {
      await axios.patch(`${API}/watchlist/${symbol}`, { strategy: newStrategy })
      // Clear old cache so new strategy triggers re-backtest
      await axios.delete(`${API}/backtest-cached/${symbol}`)
      setWatchlist(prev => prev.map(w =>
        w.symbol === symbol ? { ...w, strategy: newStrategy } : w
      ))
      // useEffect with currentStrategy dependency will trigger cache-load automatically
    } catch {}
  }

  // Open strategy params editor
  const openParamsModal = (symbol, strategy) => {
    const item = watchlist.find(w => w.symbol === symbol)
    const schema = paramsSchema[strategy] || []
    // Build initial values: merge defaults with saved custom params
    const defaults = {}
    for (const p of schema) defaults[p.name] = p.default
    const savedParams = item?.strategy_params || {}
    setEditingParams({ ...defaults, ...savedParams })
    setParamsModal({ symbol, strategy })
  }

  // Save strategy params
  const saveParams = async () => {
    if (!paramsModal) return
    try {
      await axios.patch(`${API}/watchlist/${paramsModal.symbol}`, {
        strategy: paramsModal.strategy,
        strategy_params: editingParams,
      })
      setWatchlist(prev => prev.map(w =>
        w.symbol === paramsModal.symbol ? { ...w, strategy_params: { ...editingParams } } : w
      ))
      // Clear cache so it re-runs with new params
      await axios.delete(`${API}/backtest-cached/${paramsModal.symbol}`)
    } catch {}
    setParamsModal(null)
    setEditingParams({})
  }

  // Reset params to defaults
  const resetParams = () => {
    if (!paramsModal) return
    const schema = paramsSchema[paramsModal.strategy] || []
    const defaults = {}
    for (const p of schema) defaults[p.name] = p.default
    setEditingParams(defaults)
  }

  // Run backtest
  const runBacktest = useCallback(async () => {
    if (!selectedSymbol) return

    // Increment sequence to invalidate previous in-flight request
    const seq = ++reqSeq.current

    setRunning(true)
    try {
      const res = await axios.get(`${API}/analyze`, {
        params: { symbol: selectedSymbol, freq },
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
      setRunning(false)
    }
  }, [selectedSymbol, freq])

  // Load cached backtest result from DB; if none, run fresh backtest
  const loadCachedBacktest = useCallback(async () => {
    if (!selectedSymbol) return
    // Abort if already loading or running (avoids duplicate calls from rapid switching)
    if (loading || running) return
    const strategy = getSelectedStrategy()
    const item = watchlist.find(w => w.symbol === selectedSymbol)
    const savedParams = item?.strategy_params || {}
    setLoading(true)
    try {
      const params = {}
      params.freq = freq
      params.strategy = strategy
      const res = await axios.get(`${API}/backtest-cached/${selectedSymbol}`, { params })
      if (res.data) {
        // Has cached result — populate UI directly
        const cached = res.data
        setKlineData(cached.kline || [])
        setReturnsCurve(cached.returns_curve || [])
        // Regenerate buy-and-hold benchmark from kline data
        const kline = cached.kline || []
        if (kline.length >= 1) {
          const firstPrice = kline[0].close
          const bh = kline.map(r => ({
            date: r.date,
            value: +((r.close - firstPrice) / firstPrice * 100).toFixed(2),
          }))
          setBhBenchmark(bh)
        } else {
          setBhBenchmark([])
        }
        setSignals([])
        setPositionMap({})
        setCompletedTrades(cached.trades || [])
        const trades = cached.trades || []
        const wins = trades.filter(t => t.is_profitable)
        const losses = trades.filter(t => !t.is_profitable)
        const winRate = trades.length > 0 ? (wins.length / trades.length * 100) : 0
        setStats({
          finalValue: cached.final_value,
          totalReturn: cached.total_return_pct,
          bars: kline.length,
          trades: cached.trade_count,
          winCount: cached.win_count,
          lossCount: cached.loss_count,
          winRate,
          plRatio: cached.pl_ratio || 0,
          avgPositiveReturn: cached.avg_positive_return || 0,
          avgNegativeReturn: cached.avg_negative_return || 0,
        })
        setLoading(false)
        return
      }
    } catch {}
    setLoading(false)
    // No cache — run fresh backtest
    runBacktest()
  }, [selectedSymbol, freq, runBacktest])

  // Auto-load when symbol, freq, or strategy changes (debounced 200ms)
  useEffect(() => {
    if (!selectedSymbol) return
    const strategy = watchlist.find(w => w.symbol === selectedSymbol)?.strategy || 'macross'
    const key = `${selectedSymbol}:${freq}:${strategy}`
    // Skip if already loaded this combo (avoids re-triggering on quote refresh)
    if (lastLoadKey.current === key) return
    lastLoadKey.current = key
    debounceTimer.current = setTimeout(loadCachedBacktest, 200)
  }, [selectedSymbol, freq, watchlist])

  // Resolve symbol — debounce 500ms
  const resolveCode = useCallback((code) => {
    code = code.trim()
    if (!code || code.includes(".")) {
      setResolvedSymbol(code || null)
      setResolvedName(null)
      setResolveError(null)
      return
    }
    if (resolveTimer.current) clearTimeout(resolveTimer.current)
    setResolving(true)
    setResolveError(null)
    resolveTimer.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/resolve-symbol`, { params: { code } })
        if (res.data.ambiguous && res.data.alternatives && res.data.alternatives.length > 1) {
          setAmbiguousModal({ code, alternatives: res.data.alternatives, selected: res.data.symbol, name: res.data.name || '' })
          setResolvedSymbol(null)
          setResolvedName(null)
        } else {
          setResolvedSymbol(res.data.symbol)
          setResolvedName(res.data.name || null)
        }
      } catch (e) {
        setResolveError(e.response?.data?.detail || "未找到")
        setResolvedSymbol(null)
        setResolvedName(null)
      } finally {
        setResolving(false)
      }
    }, 500)
  }, [])

  // Add symbol
  const addSymbol = async (symbol, name) => {
    const finalSymbol = symbol || resolvedSymbol || newSymbol.trim()
    const finalName = name || resolvedName || ''
    if (!finalSymbol) return
    try {
      await axios.post(`${API}/watchlist`, { symbol: finalSymbol, name: finalName, market: '' })
      setNewSymbol('')
      setResolvedSymbol(null)
      setResolvedName(null)
      setResolveError(null)
      setAmbiguousModal(null)
      await loadWatchlist()
    } catch {}
  }

  // Remove symbol
  const removeSymbol = async (symbol) => {
    try {
      await axios.delete(`${API}/watchlist/${symbol}`)
      const wasSelected = selectedSymbol === symbol
      // Manually reload to avoid stale closure on selectedSymbol
      const res = await axios.get(`${API}/watchlist`)
      setWatchlist(res.data)
      if (wasSelected) {
        setSelectedSymbol(res.data.length > 0 ? res.data[0].symbol : null)
        // Refresh quotes for the updated watchlist
        if (res.data.length > 0) {
          const symbols = res.data.map(i => i.symbol).join(",")
          axios.get(`${API}/quote`, { params: { symbols } }).then(r => {
            const quoteMap = {}
            for (const q of r.data) quoteMap[q.symbol] = q
            setQuotes(quoteMap)
          }).catch(() => {})
        }
      }
    } catch {}
  }

  // Update symbols database
  const updateDb = async () => {
    setUpdatingDb(true)
    setUpdateResult(null)
    try {
      const res = await axios.post(`${API}/update-symbols`)
      setUpdateResult(res.data)
    } catch (e) {
      setUpdateResult({ status: 'error', message: e.message })
    } finally {
      setUpdatingDb(false)
    }
  }

  // --- K-line chart ---
  const klineOption = useMemo(() => createKlineOption(klineData, completedTrades), [klineData, completedTrades])

  // --- Returns chart ---
  const cleanDates = useMemo(() => klineData.filter(d => d.open > 0 && d.close > 0 && d.high > 0 && d.low > 0).map(d => d.date), [klineData])
  const returnsOption = useMemo(() => createReturnsOption(returnsCurve, bhBenchmark, completedTrades, cleanDates), [returnsCurve, bhBenchmark, completedTrades, cleanDates])

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">QuantInvest</div>

        <div className="sidebar-section">
          <h3>自选股</h3>
        </div>

        <div className="watchlist">
          {watchlist.map(item => {
            const quote = quotes[item.symbol]
            const changePct = quote?.change_pct
            const itemStrategy = item.strategy || 'macross'
            return (
              <div
                key={item.symbol}
                className={`watchlist-item ${selectedSymbol === item.symbol ? 'active' : ''}`}
                onClick={() => setSelectedSymbol(item.symbol)}
              >
                <div>
                  <div className="watchlist-symbol">{item.symbol}</div>
                  {item.name && <div className="watchlist-name">{item.name}</div>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {quote && (
                    <>
                      {quote.price !== null && quote.price !== undefined && (
                        <span className={`watchlist-price ${changePct >= 0 ? 'positive' : 'negative'}`}>
                          {quote.price}
                        </span>
                      )}
                      {changePct !== null && changePct !== undefined && (
                        <span className={`watchlist-change ${changePct >= 0 ? 'positive' : 'negative'}`}>
                          {changePct >= 0 ? '+' : ''}{changePct}%
                        </span>
                      )}
                    </>
                  )}
                  <select
                    className="watchlist-strategy"
                    value={itemStrategy}
                    onClick={e => e.stopPropagation()}
                    onChange={e => changeStrategy(item.symbol, e.target.value)}
                  >
                    {strategies.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  <button
                    className="watchlist-gear"
                    title="策略参数"
                    onClick={(e) => { e.stopPropagation(); openParamsModal(item.symbol, itemStrategy) }}
                  >⚙</button>
                  <button
                    className="watchlist-remove"
                    onClick={(e) => { e.stopPropagation(); removeSymbol(item.symbol) }}
                  >×</button>
                </div>
              </div>
            )
          })}
        </div>

        <form className="add-form" onSubmit={e => { e.preventDefault(); addSymbol() }}>
          <div className="add-input-wrapper">
            <input
              value={newSymbol}
              onChange={e => { setNewSymbol(e.target.value); resolveCode(e.target.value) }}
              placeholder="输入代码 如 600519"
            />
            {resolving && <span className="resolve-spinner" />}
            {resolvedSymbol && !resolving && (
              <span className="resolved-preview" onClick={() => addSymbol()} title="点击添加">
                {resolvedSymbol}{resolvedName ? ` — ${resolvedName}` : ''}
              </span>
            )}
            {resolveError && <span className="resolve-error">{resolveError}</span>}
          </div>
          <button type="submit" disabled={!newSymbol.trim()}>+</button>
        </form>

        {/* Ambiguous market selection modal */}
        {ambiguousModal && (
          <div className="modal-overlay" onClick={() => setAmbiguousModal(null)}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>选择市场</h3>
              <p>代码 <strong>{ambiguousModal.code}</strong>（{ambiguousModal.name}）可能属于以下市场：</p>
              <div className="market-options">
                {ambiguousModal.alternatives.map(sym => (
                  <button
                    key={sym}
                    className={`market-option ${sym === ambiguousModal.selected ? 'selected' : ''}`}
                    onClick={() => { addSymbol(sym, ambiguousModal.name); setAmbiguousModal(null) }}
                  >
                    {sym}
                  </button>
                ))}
              </div>
              <button className="modal-cancel" onClick={() => setAmbiguousModal(null)}>取消</button>
            </div>
          </div>
        )}

        {/* Strategy params modal */}
        {paramsModal && (
          <div className="params-modal-overlay" onClick={() => { setParamsModal(null); setEditingParams({}) }}>
            <div className="params-modal" onClick={e => e.stopPropagation()}>
              <h3>策略参数</h3>
              <p className="params-subtitle">
                {paramsModal.symbol} — {paramsModal.strategy}
              </p>
              {(paramsSchema[paramsModal.strategy] || []).map(p => (
                <div key={p.name} className="param-row">
                  <span className="param-label">{p.label}</span>
                  {p.type === 'bool' ? (
                    <input
                      type="checkbox"
                      className="param-checkbox"
                      checked={!!editingParams[p.name]}
                      onChange={e => setEditingParams(prev => ({ ...prev, [p.name]: e.target.checked }))}
                    />
                  ) : (
                    <input
                      type="number"
                      step={p.type === 'float' ? 'any' : '1'}
                      className="param-input"
                      min={p.min}
                      max={p.max}
                      value={editingParams[p.name] ?? p.default}
                      onChange={e => setEditingParams(prev => ({
                        ...prev,
                        [p.name]: p.type === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value) || 0,
                      }))}
                    />
                  )}
                </div>
              ))}
              <div className="params-actions">
                <button className="params-reset-btn" onClick={resetParams}>恢复默认</button>
                <button className="params-cancel-btn" onClick={() => { setParamsModal(null); setEditingParams({}) }}>取消</button>
                <button className="params-save-btn" onClick={saveParams}>保存</button>
              </div>
            </div>
          </div>
        )}

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

        {/* Database update */}
        <div className="sidebar-section">
          <h3>数据库</h3>
          <button
            className={`db-update-btn ${updatingDb ? 'loading' : ''}`}
            onClick={updateDb}
            disabled={updatingDb}
          >
            {updatingDb ? '更新中...' : '刷新股票库'}
          </button>
          {updateResult && (
            <div className="update-result">
              {updateResult.sources && Object.entries(updateResult.sources).map(([k, v]) => (
                <div key={k} className={`update-item ${v === 'ok' ? 'success' : 'error'}`}>
                  {k}: {typeof v === 'string' && v !== 'ok' ? v.substring(0, 50) : v}
                </div>
              ))}
              {updateResult.total && <div className="update-total">{updateResult.total}</div>}
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="main">
        {/* Tab navigation */}
        <div className="tab-nav">
          {['backtest', 'report', 'optimizer'].map(tab => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'backtest' ? '单股回测' : tab === 'report' ? '批量报告' : '策略优化'}
            </button>
          ))}
        </div>

        {/* Tab: Backtest */}
        {activeTab === 'backtest' && (
          <>
        <header className="main-header">
          <h2>{selectedSymbol || '选择股票'}</h2>
          <button className="run-btn" onClick={runBacktest} disabled={loading || running}>
            {loading ? '加载中...' : running ? '回测中...' : '运行回测'}
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
                <ReactECharts key={`k-${selectedSymbol}-${getSelectedStrategy()}-${freq}`} option={klineOption} style={{ height: '100%', width: '100%' }}
                  opts={{ renderer: 'canvas' }} />
              </div>
              <div className="chart-panel equity">
                <ReactECharts key={`r-${selectedSymbol}-${getSelectedStrategy()}-${freq}`} option={returnsOption} style={{ height: '100%', width: '100%' }}
                  opts={{ renderer: 'canvas' }} />
              </div>
              {completedTrades.length > 0 && (
                <div className="trades-table-wrapper">
                  <table className="trades-table">
                    <thead>
                      <tr>
                        <th>买入日期</th>
                        <th>卖出日期</th>
                        <th>买入价</th>
                        <th>卖出价</th>
                        <th>收益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {completedTrades.map((t, i) => {
                        const pnlPct = ((t.sell_price - t.buy_price) / t.buy_price * 100).toFixed(2)
                        return (
                          <tr key={i}>
                            <td>{t.buy_date}</td>
                            <td>{t.sell_date}</td>
                            <td>{t.buy_price.toFixed(3)}</td>
                            <td>{t.sell_price.toFixed(3)}</td>
                            <td className={t.is_profitable ? 'positive' : 'negative'}>
                              {t.is_profitable ? '+' : ''}{pnlPct}%
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <div className="placeholder">
              {loading ? <><span className="loading-spinner" /> 加载中...</> : running ? <><span className="loading-spinner" /> 回测中...</> : '选择股票开始回测'}
            </div>
          )}
        </div>
          </>
        )}

        {/* Tab: Batch Report */}
        {activeTab === 'report' && (
          <BatchReportView
            watchlist={watchlist}
            freq={freq}
            setFreq={setFreq}
            reportData={reportData}
            setReportData={setReportData}
            reportRunning={reportRunning}
            setReportRunning={setReportRunning}
          />
        )}

        {/* Tab: Optimizer */}
        {activeTab === 'optimizer' && (
          <OptimizerView
            watchlist={watchlist}
            strategies={strategies}
            paramsSchema={paramsSchema}
            optStrategy={optStrategy}
            setOptStrategy={setOptStrategy}
            optSymbol={optSymbol}
            setOptSymbol={setOptSymbol}
            optParamRanges={optParamRanges}
            setOptParamRanges={setOptParamRanges}
            optResults={optResults}
            setOptResults={setOptResults}
            optRunning={optRunning}
            setOptRunning={setOptRunning}
          />
        )}
      </main>
    </div>
  )
}


/* ===== Batch Report View ===== */

function BatchReportView({ watchlist, freq, setFreq, reportData, setReportData, reportRunning, setReportRunning }) {
  const [signalData, setSignalData] = useState(null)
  const [signalLoading, setSignalLoading] = useState(false)

  const runBatch = async () => {
    if (watchlist.length === 0) return
    setReportRunning(true)
    setReportData(null)
    try {
      const symbols = watchlist.map(w => w.symbol)
      const res = await axios.post(`${API}/batch-backtest`, { symbols, freq })
      setReportData(res.data)
    } catch (e) {
      console.error('Batch backtest failed:', e)
    } finally {
      setReportRunning(false)
    }
  }

  const runSignals = async () => {
    if (watchlist.length === 0) return
    setSignalLoading(true)
    setSignalData(null)
    try {
      const symbols = watchlist.map(w => w.symbol)
      const res = await axios.post(`${API}/signals`, { symbols, freq })
      setSignalData(res.data)
    } catch (e) {
      console.error('Signals fetch failed:', e)
    } finally {
      setSignalLoading(false)
    }
  }

  return (
    <div className="report-view">
      <div className="report-header">
        <h2>自选股批量回测报告</h2>
        <div className="report-controls">
          <div className="freq-group">
            {['daily', 'weekly', '60min', '30min'].map(f => (
              <button key={f} className={`freq-btn ${freq === f ? 'active' : ''}`} onClick={() => setFreq(f)}>{f}</button>
            ))}
          </div>
          <button className="run-btn" onClick={runBatch} disabled={reportRunning || watchlist.length === 0}>
            {reportRunning ? <><span className="loading-spinner" />回测中...</> : '开始批量回测'}
          </button>
          <button className="run-btn signal-btn" onClick={runSignals} disabled={signalLoading || watchlist.length === 0}>
            {signalLoading ? <><span className="loading-spinner" />获取中...</> : '策略信号'}
          </button>
        </div>
      </div>

      {/* Strategy Signals Section */}
      {signalData && signalData.results && (
        <div className="signals-section">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
            <h3 style={{margin:0}}>策略信号（最新持仓状态）</h3>
            <span style={{fontSize:11,color:'var(--text-secondary)'}}>
              {signalData.results[0]?.cached ? `⏱ 缓存 (${signalData.results[0]?.updated_at})` : '🔄 实时计算'}
            </span>
          </div>
          <table className="report-table signal-table">
            <thead>
              <tr>
                <th rowSpan={2}>股票代码</th>
                <th colSpan={8}>策略信号</th>
              </tr>
              <tr>
                {signalData.results[0]?.signals.map(s => (
                  <th key={s.strategy} className="strat-header">{s.strategy}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {signalData.results.map(r => (
                <tr key={r.symbol}>
                  <td className="symbol-cell">{r.symbol}</td>
                  {r.signals.map(s => (
                    <td key={s.strategy} className={`signal-cell signal-${s.signal.toLowerCase()}`}>
                      {s.signal === 'ERROR' ? <span className="error-text">错误</span> : s.signal === 'LONG' ? '🟢 持仓' : '⚪ 空仓'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {reportData && reportData.results && (
        <div className="report-table-wrapper">
          <table className="report-table">
            <thead>
              <tr>
                <th rowSpan={2}>股票代码</th>
                <th colSpan={8}>策略对比</th>
              </tr>
              <tr>
                {reportData.results[0]?.strategies.map(s => (
                  <th key={s.strategy} className="strat-header">{s.strategy}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reportData.results.map(r => (
                <tr key={r.symbol}>
                  <td className="symbol-cell">{r.symbol}</td>
                  {r.strategies.map(s => (
                    <td key={s.strategy} className={s.total_return_pct >= 0 ? 'positive' : 'negative'}>
                      {s.error ? <span className="error-text">错误</span> : (
                        <div className="strat-cell">
                          <div className="return-val">{s.total_return_pct >= 0 ? '+' : ''}{s.total_return_pct}%</div>
                          <div className="meta-row">
                            <span>胜率{s.win_rate}%</span>
                            <span>DD{s.max_drawdown_pct}%</span>
                          </div>
                          <div className="meta-row"><span>{s.trade_count}笔</span></div>
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!reportData && !reportRunning && (
        <div className="placeholder">
          {watchlist.length === 0 ? '自选股为空，请先添加股票' : '点击"开始批量回测"对所有自选股运行全部策略'}
        </div>
      )}
    </div>
  )
}


/* ===== Optimizer View ===== */

function OptimizerView({ watchlist, strategies, paramsSchema, optStrategy, setOptStrategy, optSymbol, setOptSymbol, optParamRanges, setOptParamRanges, optResults, setOptResults, optRunning, setOptRunning }) {
  // When strategy changes, auto-fill param ranges from schema defaults
  useEffect(() => {
    const schema = paramsSchema[optStrategy] || []
    if (schema.length > 0 && Object.keys(optParamRanges).length === 0) {
      const ranges = {}
      for (const p of schema) {
        if (p.type === 'bool') continue  // skip bool params for optimization
        const d = p.default
        if (p.type === 'int') {
          ranges[p.name] = { min: Math.max(1, Math.floor(d * 0.5)), max: Math.ceil(d * 2), step: 1 }
        } else {
          ranges[p.name] = { min: Math.max(0.001, +(d * 0.5).toFixed(4)), max: +(d * 2).toFixed(4), step: +(p.name.includes('pct') || p.name.includes('threshold')) ? 0.01 : 0.1 }
        }
      }
      setOptParamRanges(ranges)
    }
    // If switching strategies, clear old ranges
    if (schema.length > 0 && Object.keys(optParamRanges).length > 0) {
      const hasMatch = schema.some(p => p.name in optParamRanges)
      if (!hasMatch) {
        const ranges = {}
        for (const p of schema) {
          if (p.type === 'bool') continue
          const d = p.default
          if (p.type === 'int') {
            ranges[p.name] = { min: Math.max(1, Math.floor(d * 0.5)), max: Math.ceil(d * 2), step: 1 }
          } else {
            ranges[p.name] = { min: Math.max(0.001, +(d * 0.5).toFixed(4)), max: +(d * 2).toFixed(4), step: 0.1 }
          }
        }
        setOptParamRanges(ranges)
      }
    }
  }, [optStrategy])

  const runOptimize = async () => {
    if (!optSymbol || !optStrategy) return
    setOptRunning(true)
    setOptResults(null)
    try {
      const res = await axios.post(`${API}/optimize`, {
        symbol: optSymbol,
        strategy: optStrategy,
        freq: 'daily',
        params: optParamRanges,
      })
      setOptResults(res.data)
    } catch (e) {
      console.error('Optimization failed:', e)
    } finally {
      setOptRunning(false)
    }
  }

  const schema = paramsSchema[optStrategy] || []

  return (
    <div className="optimizer-view">
      <h2>策略参数优化</h2>
      <div className="opt-config">
        <div className="opt-row">
          <label>股票</label>
          <select value={optSymbol} onChange={e => setOptSymbol(e.target.value)}>
            <option value="">选择股票</option>
            {watchlist.map(w => <option key={w.symbol} value={w.symbol}>{w.symbol}{w.name ? ` ${w.name}` : ''}</option>)}
          </select>
        </div>
        <div className="opt-row">
          <label>策略</label>
          <select value={optStrategy} onChange={e => setOptStrategy(e.target.value)}>
            {strategies.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="param-ranges">
          <h3>参数范围</h3>
          {schema.filter(p => p.type !== 'bool').map(p => (
            <div key={p.name} className="range-row">
              <span className="range-label">{p.label}</span>
              <div className="range-inputs">
                <input type="number" step={p.type === 'float' ? 'any' : '1'} placeholder="最小"
                  value={optParamRanges[p.name]?.min ?? ''}
                  onChange={e => setOptParamRanges(prev => ({ ...prev, [p.name]: { ...prev[p.name], min: parseFloat(e.target.value) || 0 } }))} />
                <span className="range-sep">—</span>
                <input type="number" step={p.type === 'float' ? 'any' : '1'} placeholder="最大"
                  value={optParamRanges[p.name]?.max ?? ''}
                  onChange={e => setOptParamRanges(prev => ({ ...prev, [p.name]: { ...prev[p.name], max: parseFloat(e.target.value) || 0 } }))} />
                <span className="range-sep">步长</span>
                <input type="number" step="any" placeholder="步长"
                  value={optParamRanges[p.name]?.step ?? ''}
                  onChange={e => setOptParamRanges(prev => ({ ...prev, [p.name]: { ...prev[p.name], step: parseFloat(e.target.value) || 1 } }))} />
              </div>
            </div>
          ))}
        </div>

        <button className="run-btn opt-run-btn" onClick={runOptimize} disabled={optRunning || !optSymbol}>
          {optRunning ? <><span className="loading-spinner" />优化中...</> : '开始优化'}
        </button>
      </div>

      {optResults && (
        <div className="opt-results">
          <div className="opt-summary">
            共测试 <strong>{optResults.total_combinations}</strong> 组参数，成功 <strong>{optResults.evaluated}</strong> 组
          </div>

          <div className="opt-metrics-grid">
            <div className="opt-metric-card">
              <h3>🏆 胜率最高 Top3</h3>
              <table className="opt-table">
                <thead><tr><th>参数</th><th>收益率</th><th>胜率</th><th>最大回撤</th><th>交易次数</th></tr></thead>
                <tbody>
                  {(optResults.best_win_rate || []).map((r, i) => (
                    <tr key={i}><td>{formatParams(r.params)}</td><td className={r.total_return_pct >= 0 ? 'positive' : 'negative'}>{r.total_return_pct}%</td><td className="positive">{r.win_rate}%</td><td>{r.max_drawdown_pct}%</td><td>{r.trade_count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="opt-metric-card">
              <h3>💰 收益最高 Top3</h3>
              <table className="opt-table">
                <thead><tr><th>参数</th><th>收益率</th><th>胜率</th><th>最大回撤</th><th>交易次数</th></tr></thead>
                <tbody>
                  {(optResults.best_return || []).map((r, i) => (
                    <tr key={i}><td>{formatParams(r.params)}</td><td className={r.total_return_pct >= 0 ? 'positive' : 'negative'}>{r.total_return_pct}%</td><td>{r.win_rate}%</td><td>{r.max_drawdown_pct}%</td><td>{r.trade_count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="opt-metric-card">
              <h3>📉 回撤最小 Top3</h3>
              <table className="opt-table">
                <thead><tr><th>参数</th><th>收益率</th><th>胜率</th><th>最大回撤</th><th>交易次数</th></tr></thead>
                <tbody>
                  {(optResults.best_drawdown || []).map((r, i) => (
                    <tr key={i}><td>{formatParams(r.params)}</td><td className={r.total_return_pct >= 0 ? 'positive' : 'negative'}>{r.total_return_pct}%</td><td>{r.win_rate}%</td><td className="positive">{r.max_drawdown_pct}%</td><td>{r.trade_count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {!optResults && !optRunning && (
        <div className="placeholder">配置参数范围后点击"开始优化"</div>
      )}
    </div>
  )
}

function formatParams(params) {
  return Object.entries(params).map(([k, v]) => `${k}=${v}`).join(', ')
}


/* ===== ECharts option builders ===== */

function createKlineOption(kline, completedTrades) {
  // Filter out zero-value rows (bad data from baostock)
  const clean = kline.filter(d => d.open > 0 && d.close > 0 && d.high > 0 && d.low > 0)
  const dates = clean.map(d => d.date)
  const ohlc = clean.map(d => [d.open, d.close, d.low, d.high])
  const volumes = clean.map(d => d.volume)

  // 34-day Simple Moving Average
  const sma34 = clean.map((_, i) => {
    if (i < 33) return null
    let sum = 0
    for (let j = i - 33; j <= i; j++) sum += clean[j].close
    return +(sum / 34).toFixed(2)
  })

  // Chip cost curves (COST function similar to TongDaXin):
  // For each day, maintain a chip distribution pool and find the price at which
  // N% of chips are profitable (i.e., current price > chip cost price).
  const chipCostCurves = (() => {
    // Price bins: use a fine-grained grid around the price range
    const prices = clean.map(d => d.close)
    const minP = Math.min(...prices) * 0.95
    const maxP = Math.max(...prices) * 1.05
    const binWidth = (maxP - minP) / 200  // 200 price bins
    const numBins = 200

    // Decay factor per day (half-life ~ 60 days, simulating chip turnover)
    const decay = Math.pow(0.5, 1 / 60)

    // Initialize chip distribution array (price bins)
    let chips = new Array(numBins).fill(0)

    function priceToBin(p) {
      return Math.min(numBins - 1, Math.max(0, Math.floor((p - minP) / binWidth)))
    }

    const cost20 = new Array(clean.length).fill(null)
    const cost50 = new Array(clean.length).fill(null)
    const cost80 = new Array(clean.length).fill(null)

    for (let i = 0; i < clean.length; i++) {
      const d = clean[i]
      const vol = d.volume || 0

      // Decay existing chips
      for (let b = 0; b < numBins; b++) {
        chips[b] *= decay
      }

      // Add new chips at today's close price (Gaussian spread ±1.5%)
      const centerBin = priceToBin(d.close)
      const spread = Math.max(2, Math.floor(0.015 * (maxP - minP) / binWidth))
      for (let offset = -spread; offset <= spread; offset++) {
        const bin = centerBin + offset
        if (bin >= 0 && bin < numBins) {
          const weight = Math.exp(-(offset * offset) / (2 * spread * 0.3))
          chips[bin] += vol * weight
        }
      }

      // Calculate cumulative distribution from low to high price
      let totalChips = chips.reduce((s, v) => s + v, 0)
      if (totalChips === 0) {
        continue
      }

      let cumChips = 0
      for (let b = 0; b < numBins; b++) {
        cumChips += chips[b]
        const cumPct = cumChips / totalChips * 100
        const binPrice = minP + (b + 0.5) * binWidth

        if (cumPct >= 20 && cost20[i] === null) cost20[i] = +(binPrice).toFixed(2)
        if (cumPct >= 50 && cost50[i] === null) cost50[i] = +(binPrice).toFixed(2)
        if (cumPct >= 80 && cost80[i] === null) cost80[i] = +(binPrice).toFixed(2)
      }

      // Forward-fill: use previous day's value if not computed
      if (i > 0) {
        if (cost20[i] === null) cost20[i] = cost20[i - 1]
        if (cost50[i] === null) cost50[i] = cost50[i - 1]
        if (cost80[i] === null) cost80[i] = cost80[i - 1]
      }
    }

    return { cost20, cost50, cost80 }
  })()

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
    legend: { data: ['K线', 'MA34', '筹码20%', '筹码50%', '筹码80%', '成交量'], textStyle: { color: '#9ca3af' }, top: 0 },
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
        name: 'MA34',
        type: 'line',
        data: sma34,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#a78bfa' },
      },
      {
        name: '筹码20%',
        type: 'line',
        data: chipCostCurves.cost20,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: 'rgba(16,185,129,0.8)' },
      },
      {
        name: '筹码50%',
        type: 'line',
        data: chipCostCurves.cost50,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: 'rgba(245,158,11,0.8)' },
      },
      {
        name: '筹码80%',
        type: 'line',
        data: chipCostCurves.cost80,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: 'rgba(239,68,68,0.8)' },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: clean[i].close >= clean[i].open ? 'rgba(16,185,129,0.5)' : 'rgba(239,68,68,0.5)' },
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
          const v = p.value ?? 0
          const sign = v >= 0 ? '+' : ''
          tip += `<span style="display:inline-block;margin-right:8px;color:${p.color}">${p.seriesName}: ${sign}${v.toFixed(2)}%</span>`
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
