import { useState } from 'react'
import axios from 'axios'

const API = '/api'

export function Sidebar({
  watchlist, selectedSymbol, setSelectedSymbol, quotes, strategies, paramsSchema,
  changeStrategy, removeSymbol, addSymbol, getSymbolStrategy, updateSymbolParams,
  freq, setFreq, newSymbol, setNewSymbol, resolveCode,
  resolving, resolvedSymbol, resolvedName, resolveError, ambiguousModal, dismissAmbiguous,
  updatingDb, setUpdatingDb, updateResult, setUpdateResult,
}) {
  const [paramsModal, setParamsModal] = useState(null)
  const [editingParams, setEditingParams] = useState({})

  const openParamsModal = (symbol, strategy) => {
    const item = watchlist.find(w => w.symbol === symbol)
    const schema = paramsSchema[strategy] || []
    const defaults = {}
    for (const p of schema) defaults[p.name] = p.default
    const savedParams = item?.strategy_params || {}
    setEditingParams({ ...defaults, ...savedParams })
    setParamsModal({ symbol, strategy })
  }

  const saveParams = async () => {
    if (!paramsModal) return
    try {
      await axios.patch(`${API}/watchlist/${paramsModal.symbol}`, {
        strategy: paramsModal.strategy,
        strategy_params: editingParams,
      })
      updateSymbolParams(paramsModal.symbol, paramsModal.strategy, editingParams)
    } catch {}
    setParamsModal(null)
    setEditingParams({})
  }

  const resetParams = () => {
    if (!paramsModal) return
    const schema = paramsSchema[paramsModal.strategy] || []
    const defaults = {}
    for (const p of schema) defaults[p.name] = p.default
    setEditingParams(defaults)
  }

  const handleUpdateDb = async () => {
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

  return (
    <aside className="sidebar">
      <div className="sidebar-header">QuantInvest</div>

      <div className="sidebar-section">
        <h3>自选股</h3>
      </div>

      <div className="watchlist" role="listbox" aria-label="自选股列表">
        {watchlist.map(item => (
          <WatchlistItem
            key={item.symbol}
            item={item}
            quote={quotes[item.symbol]}
            isSelected={selectedSymbol === item.symbol}
            strategies={strategies}
            onSelect={() => setSelectedSymbol(item.symbol)}
            onChangeStrategy={(s) => changeStrategy(item.symbol, s)}
            onOpenParams={() => openParamsModal(item.symbol, item.strategy || 'macross')}
            onRemove={() => removeSymbol(item.symbol)}
          />
        ))}
      </div>

      <form className="add-form" onSubmit={e => { e.preventDefault(); addSymbol() }}>
        <div className="add-input-wrapper">
          <input
            value={newSymbol}
            onChange={e => { setNewSymbol(e.target.value); resolveCode(e.target.value) }}
            placeholder="输入代码 如 600519"
            aria-label="股票代码"
          />
          {resolving && <span className="resolve-spinner" />}
          {resolvedSymbol && !resolving && (
            <span className="resolved-preview" onClick={() => addSymbol()} title="点击添加">
              {resolvedSymbol}{resolvedName ? ` — ${resolvedName}` : ''}
            </span>
          )}
          {resolveError && <span className="resolve-error">{resolveError}</span>}
        </div>
        <button type="submit" disabled={!newSymbol.trim()} aria-label="添加股票">+</button>
      </form>

      {/* Ambiguous market modal */}
      {ambiguousModal && (
        <div className="modal-overlay" onClick={dismissAmbiguous}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>选择市场</h3>
            <p>代码 <strong>{ambiguousModal.code}</strong>（{ambiguousModal.name}）可能属于以下市场：</p>
            <div className="market-options">
              {ambiguousModal.alternatives.map(sym => (
                <button
                  key={sym}
                  className={`market-option ${sym === ambiguousModal.selected ? 'selected' : ''}`}
                  onClick={() => { addSymbol(sym, ambiguousModal.name); dismissAmbiguous() }}
                >
                  {sym}
                </button>
              ))}
            </div>
            <button className="modal-cancel" onClick={dismissAmbiguous}>取消</button>
          </div>
        </div>
      )}

      {/* Strategy params modal */}
      {paramsModal && (
        <div className="params-modal-overlay" onClick={() => { setParamsModal(null); setEditingParams({}) }}>
          <div className="params-modal" onClick={e => e.stopPropagation()}>
            <h3>策略参数</h3>
            <p className="params-subtitle">{paramsModal.symbol} — {paramsModal.strategy}</p>
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

      {/* Frequency selector */}
      <div className="freq-selector">
        <div className="sidebar-section" style={{ padding: 0 }}>
          <h3>级别</h3>
          <FreqSelector value={freq} onChange={setFreq} />
        </div>
      </div>

      {/* Database update */}
      <div className="sidebar-section">
        <h3>数据库</h3>
        <button
          className={`db-update-btn ${updatingDb ? 'loading' : ''}`}
          onClick={handleUpdateDb}
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
  )
}

/* --- Sub-components --- */

function WatchlistItem({ item, quote, isSelected, strategies, onSelect, onChangeStrategy, onOpenParams, onRemove }) {
  const changePct = quote?.change_pct
  const itemStrategy = item.strategy || 'macross'
  return (
    <div
      role="option"
      aria-selected={isSelected}
      className={`watchlist-item ${isSelected ? 'active' : ''}`}
      onClick={onSelect}
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
          onChange={e => onChangeStrategy(e.target.value)}
          aria-label="策略"
        >
          {strategies.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="watchlist-gear" title="策略参数" onClick={e => { e.stopPropagation(); onOpenParams() }}>⚙</button>
        <button className="watchlist-remove" aria-label="移除" onClick={e => { e.stopPropagation(); onRemove() }}>×</button>
      </div>
    </div>
  )
}

function FreqSelector({ value, onChange }) {
  return (
    <div className="freq-group" role="radiogroup" aria-label="时间级别">
      {['daily', 'weekly', '60min', '30min'].map(f => (
        <button
          key={f}
          type="button"
          role="radio"
          aria-checked={value === f}
          className={`freq-btn ${value === f ? 'active' : ''}`}
          onClick={() => onChange(f)}
        >{f}</button>
      ))}
    </div>
  )
}
