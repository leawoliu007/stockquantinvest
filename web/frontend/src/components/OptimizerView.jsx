import { useState, useEffect } from 'react'
import axios from 'axios'
import { formatParams } from '../utils/stats'

const API = '/api'

export function OptimizerView({ watchlist, strategies, paramsSchema }) {
  const [optStrategy, setOptStrategy] = useState('macross')
  const [optSymbol, setOptSymbol] = useState('')
  const [optParamRanges, setOptParamRanges] = useState({})
  const [optResults, setOptResults] = useState(null)
  const [optRunning, setOptRunning] = useState(false)

  // Auto-fill param ranges when strategy changes
  useEffect(() => {
    const schema = paramsSchema[optStrategy] || []
    if (schema.length === 0) return

    const buildRanges = () => {
      const ranges = {}
      for (const p of schema) {
        if (p.type === 'bool') continue
        const d = p.default
        if (p.type === 'int') {
          ranges[p.name] = { min: Math.max(1, Math.floor(d * 0.5)), max: Math.ceil(d * 2), step: 1 }
        } else {
          const step = (p.name.includes('pct') || p.name.includes('threshold')) ? 0.01 : 0.1
          ranges[p.name] = { min: Math.max(0.001, +(d * 0.5).toFixed(4)), max: +(d * 2).toFixed(4), step }
        }
      }
      return ranges
    }

    // Fill if empty or strategy mismatch
    if (Object.keys(optParamRanges).length === 0) {
      setOptParamRanges(buildRanges())
    } else {
      const hasMatch = schema.some(p => p.name in optParamRanges)
      if (!hasMatch) setOptParamRanges(buildRanges())
    }
  }, [optStrategy, paramsSchema])

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
            <ParamRangeRow
              key={p.name}
              param={p}
              range={optParamRanges[p.name]}
              onChange={range => setOptParamRanges(prev => ({ ...prev, [p.name]: range }))}
            />
          ))}
        </div>

        <button className="run-btn opt-run-btn" onClick={runOptimize} disabled={optRunning || !optSymbol}>
          {optRunning ? <><span className="loading-spinner" />优化中...</> : '开始优化'}
        </button>
      </div>

      {optResults && <OptResults results={optResults} />}

      {!optResults && !optRunning && (
        <div className="placeholder">配置参数范围后点击"开始优化"</div>
      )}
    </div>
  )
}

function ParamRangeRow({ param, range, onChange }) {
  return (
    <div key={param.name} className="range-row">
      <span className="range-label">{param.label}</span>
      <div className="range-inputs">
        <input type="number" step={param.type === 'float' ? 'any' : '1'} placeholder="最小"
          value={range?.min ?? ''}
          onChange={e => onChange({ ...range, min: parseFloat(e.target.value) || 0 })} />
        <span className="range-sep">—</span>
        <input type="number" step={param.type === 'float' ? 'any' : '1'} placeholder="最大"
          value={range?.max ?? ''}
          onChange={e => onChange({ ...range, max: parseFloat(e.target.value) || 0 })} />
        <span className="range-sep">步长</span>
        <input type="number" step="any" placeholder="步长"
          value={range?.step ?? ''}
          onChange={e => onChange({ ...range, step: parseFloat(e.target.value) || 1 })} />
      </div>
    </div>
  )
}

function OptResults({ results }) {
  return (
    <div className="opt-results">
      <div className="opt-summary">
        共测试 <strong>{results.total_combinations}</strong> 组参数，成功 <strong>{results.evaluated}</strong> 组
      </div>
      <div className="opt-metrics-grid">
        <OptMetricCard title="🏆 胜率最高 Top3" data={results.best_win_rate || []} highlight="win_rate" />
        <OptMetricCard title="💰 收益最高 Top3" data={results.best_return || []} highlight="total_return_pct" />
        <OptMetricCard title="📉 回撤最小 Top3" data={results.best_drawdown || []} highlight="max_drawdown_pct" />
      </div>
    </div>
  )
}

function OptMetricCard({ title, data, highlight }) {
  return (
    <div className="opt-metric-card">
      <h3>{title}</h3>
      <table className="opt-table">
        <thead><tr><th>参数</th><th>收益率</th><th>胜率</th><th>最大回撤</th><th>交易次数</th></tr></thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={i}>
              <td>{formatParams(r.params)}</td>
              <td className={r.total_return_pct >= 0 ? 'positive' : 'negative'}>{r.total_return_pct}%</td>
              <td className={highlight === 'win_rate' ? 'positive' : ''}>{r.win_rate}%</td>
              <td className={highlight === 'max_drawdown_pct' ? 'positive' : ''}>{r.max_drawdown_pct}%</td>
              <td>{r.trade_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
