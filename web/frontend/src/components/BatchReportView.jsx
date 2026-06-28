import { useState } from 'react'
import axios from 'axios'

const API = '/api'

export function BatchReportView({ watchlist, freq, setFreq }) {
  const [reportData, setReportData] = useState(null)
  const [reportRunning, setReportRunning] = useState(false)
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
          <FreqSelector value={freq} onChange={setFreq} />
          <button className="run-btn" onClick={runBatch} disabled={reportRunning || watchlist.length === 0}>
            {reportRunning ? <><span className="loading-spinner" />回测中...</> : '开始批量回测'}
          </button>
          <button className="run-btn signal-btn" onClick={runSignals} disabled={signalLoading || watchlist.length === 0}>
            {signalLoading ? <><span className="loading-spinner" />获取中...</> : '策略信号'}
          </button>
        </div>
      </div>

      {signalData && signalData.results && (
        <SignalsTable data={signalData.results} />
      )}

      {reportData && reportData.results && (
        <ReportTable data={reportData.results} />
      )}

      {!reportData && !reportRunning && (
        <div className="placeholder">
          {watchlist.length === 0 ? '自选股为空，请先添加股票' : '点击"开始批量回测"对所有自选股运行全部策略'}
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
  return (
    <div className="signals-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>策略信号（最新持仓状态）</h3>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          {results[0]?.cached ? `⏱ 缓存 (${results[0]?.updated_at})` : '🔄 实时计算'}
        </span>
      </div>
      <table className="report-table signal-table">
        <thead>
          <tr><th rowSpan={2}>股票代码</th><th colSpan={8}>策略信号</th></tr>
          <tr>{results[0]?.signals.map(s => <th key={s.strategy} className="strat-header">{s.strategy}</th>)}</tr>
        </thead>
        <tbody>
          {results.map(r => (
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
  )
}

function ReportTable({ results }) {
  return (
    <div className="report-table-wrapper">
      <table className="report-table">
        <thead>
          <tr><th rowSpan={2}>股票代码</th><th colSpan={8}>策略对比</th></tr>
          <tr>{results[0]?.strategies.map(s => <th key={s.strategy} className="strat-header">{s.strategy}</th>)}</tr>
        </thead>
        <tbody>
          {results.map(r => (
            <tr key={r.symbol}>
              <td className="symbol-cell">{r.symbol}</td>
              {r.strategies.map(s => (
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
