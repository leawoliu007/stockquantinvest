import { useState } from 'react'
import axios from 'axios'

const API = '/api'

export function BatchReportView({ watchlist, freq, setFreq }) {
  const [reportData, setReportData] = useState(null)
  const [reportRunning, setReportRunning] = useState(false)
  const [reportError, setReportError] = useState(null)
  const [signalData, setSignalData] = useState(null)
  const [signalLoading, setSignalLoading] = useState(false)
  const [signalError, setSignalError] = useState(null)

  const wl = Array.isArray(watchlist) ? watchlist : []

  const runBatch = async () => {
    if (wl.length === 0) return
    setReportRunning(true)
    setReportData(null)
    setReportError(null)
    try {
      const symbols = wl.map(w => w.symbol)
      const res = await axios.post(`${API}/batch-backtest`, { symbols, freq }, {
        timeout: 600000, // 10 min timeout for batch
      })
      setReportData(res.data)
    } catch (e) {
      console.error('Batch backtest failed:', e)
      setReportError(e.message || '回测失败')
    } finally {
      setReportRunning(false)
    }
  }

  const runSignals = async () => {
    if (wl.length === 0) return
    setSignalLoading(true)
    setSignalData(null)
    setSignalError(null)
    try {
      const symbols = wl.map(w => w.symbol)
      const res = await axios.post(`${API}/signals`, { symbols, freq }, {
        timeout: 300000, // 5 min timeout for signals
      })
      setSignalData(res.data)
    } catch (e) {
      console.error('Signals fetch failed:', e)
      setSignalError(e.message || '获取信号失败')
    } finally {
      setSignalLoading(false)
    }
  }

  return (
    <div className="report-view">
      <div className="report-header">
        <h2>自选股批量回测报告</h2>
        <div className="report-controls">
          <FreqSelector value={freq} onChange={setFreq} />
          <button className="run-btn" onClick={runBatch} disabled={reportRunning || wl.length === 0}>
            {reportRunning ? <><span className="loading-spinner" />回测中...</> : '开始批量回测'}
          </button>
          <button className="run-btn signal-btn" onClick={runSignals} disabled={signalLoading || wl.length === 0}>
            {signalLoading ? <><span className="loading-spinner" />获取中...</> : '策略信号'}
          </button>
        </div>
      </div>

      {signalError && (
        <div className="error-banner" style={{ padding: '12px 16px', marginBottom: 12, background: '#fee', border: '1px solid #fcc', borderRadius: 6 }}>
          ⚠️ 策略信号获取失败: {signalError}
        </div>
      )}

      {signalData && signalData.results && (
        <SignalsTable data={signalData.results} />
      )}

      {reportError && (
        <div className="error-banner" style={{ padding: '12px 16px', marginBottom: 12, background: '#fee', border: '1px solid #fcc', borderRadius: 6 }}>
          ⚠️ 批量回测失败: {reportError}
        </div>
      )}

      {reportData && reportData.results && (
        <ReportTable data={reportData.results} />
      )}

      {!reportData && !reportRunning && !reportError && (
        <div className="placeholder">
          {wl.length === 0 ? '自选股为空，请先添加股票' : `点击"开始批量回测"对所有自选股运行全部策略（${wl.length} 只股票 × 8 个策略）`}
        </div>
      )}
    </div>
  )
}

function FreqSelector({ value, onChange }) {
  return (
    <div className="freq-group">
      {['daily', 'weekly', '60min', '30min'].map(f => (
        <button key={f} type="button" className={`freq-btn ${value === f ? 'active' : ''}`} onClick={() => onChange(f)}>{f}</button>
      ))}
    </div>
  )
}

function SignalsTable({ results }) {
  const safeResults = Array.isArray(results) ? results : []
  const firstSignals = safeResults[0]?.signals || []

  return (
    <div className="signals-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>策略信号（最新持仓状态）</h3>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          {safeResults[0]?.cached ? `⏱ 缓存 (${safeResults[0]?.updated_at})` : '🔄 实时计算'}
        </span>
      </div>
      <table className="report-table signal-table">
        <thead>
          <tr><th rowSpan={2}>股票代码</th><th colSpan={8}>策略信号</th></tr>
          <tr>{firstSignals.map(s => <th key={s.strategy} className="strat-header">{s.strategy}</th>)}</tr>
        </thead>
        <tbody>
          {safeResults.map(r => (
            <tr key={r.symbol}>
              <td className="symbol-cell">{r.symbol}</td>
              {(r.signals || []).map(s => (
                <td key={s.strategy} className={`signal-cell signal-${s.signal.toLowerCase()}`}>
                  {s.signal === 'ERROR' ? <span className="error-text">错误</span> : s.signal === 'LONG' ? '🟢 持仓' : '⚪ 空仓'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReportTable({ results }) {
  const safeResults = Array.isArray(results) ? results : []
  const firstStrategies = safeResults[0]?.strategies || []

  return (
    <div className="report-table-wrapper">
      <table className="report-table">
        <thead>
          <tr><th rowSpan={2}>股票代码</th><th colSpan={8}>策略对比</th></tr>
          <tr>{firstStrategies.map(s => <th key={s.strategy} className="strat-header">{s.strategy}</th>)}</tr>
        </thead>
        <tbody>
          {safeResults.map(r => (
            <tr key={r.symbol}>
              <td className="symbol-cell">{r.symbol}</td>
              {(r.strategies || []).map(s => (
                <td key={s.strategy} className={s.total_return_pct >= 0 ? 'positive' : 'negative'}>
                  {s.error ? <span className="error-text">错误</span> : (
                    <div className="strat-cell">
                      <div className="return-val">{s.total_return_pct >= 0 ? '+' : ''}{s.total_return_pct}%</div>
                      <div className="meta-row"><span>胜率{s.win_rate}%</span><span>DD{s.max_drawdown_pct}%</span></div>
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
  )
}
