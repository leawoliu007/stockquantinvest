import { useState } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Sidebar } from './components/Sidebar'
import { BacktestView } from './components/BacktestView'
import { BatchReportView } from './components/BatchReportView'
import { OptimizerView } from './components/OptimizerView'
import { useWatchlist } from './hooks/useWatchlist'
import { useSymbolResolver } from './hooks/useSymbolResolver'
import { useBacktest } from './hooks/useBacktest'

export default function App() {
  const [activeTab, setActiveTab] = useState('backtest')
  const [newSymbol, setNewSymbol] = useState('')
  const [freq, setFreq] = useState('daily')
  const [updatingDb, setUpdatingDb] = useState(false)
  const [updateResult, setUpdateResult] = useState(null)

  // Hooks
  const {
    watchlist, selectedSymbol, setSelectedSymbol, quotes, strategies, paramsSchema,
    changeStrategy, addSymbol, removeSymbol, getSymbolStrategy, updateSymbolParams,
  } = useWatchlist()

  const {
    resolvedSymbol, resolvedName, resolving, resolveError, ambiguousModal,
    resolveCode, dismissAmbiguous,
  } = useSymbolResolver()

  const {
    loading, running, klineData, returnsCurve, bhBenchmark,
    completedTrades, stats, runBacktest,
  } = useBacktest(selectedSymbol, freq, getSymbolStrategy)

  // Add symbol with resolver integration
  const handleAddSymbol = async () => {
    const finalSymbol = resolvedSymbol || newSymbol.trim()
    const finalName = resolvedName || ''
    if (!finalSymbol) return
    await addSymbol(finalSymbol, finalName)
    setNewSymbol('')
    dismissAmbiguous()
  }

  return (
    <ErrorBoundary>
      <div className="app">
        {/* Sidebar */}
        <Sidebar
          watchlist={watchlist}
          selectedSymbol={selectedSymbol}
          setSelectedSymbol={setSelectedSymbol}
          quotes={quotes}
          strategies={strategies}
          paramsSchema={paramsSchema}
          changeStrategy={changeStrategy}
          removeSymbol={removeSymbol}
          addSymbol={handleAddSymbol}
          getSymbolStrategy={getSymbolStrategy}
          updateSymbolParams={updateSymbolParams}
          freq={freq}
          setFreq={setFreq}
          newSymbol={newSymbol}
          setNewSymbol={setNewSymbol}
          resolveCode={resolveCode}
          resolving={resolving}
          resolvedSymbol={resolvedSymbol}
          resolvedName={resolvedName}
          resolveError={resolveError}
          ambiguousModal={ambiguousModal}
          dismissAmbiguous={dismissAmbiguous}
          updatingDb={updatingDb}
          setUpdatingDb={setUpdatingDb}
          updateResult={updateResult}
          setUpdateResult={setUpdateResult}
        />

        {/* Main content */}
        <main className="main">
          <div className="tab-nav" role="tablist">
            {[
              { id: 'backtest', label: '单股回测' },
              { id: 'report', label: '批量报告' },
              { id: 'optimizer', label: '策略优化' },
            ].map(tab => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'backtest' && (
            <BacktestView
              selectedSymbol={selectedSymbol}
              loading={loading}
              running={running}
              stats={stats}
              klineData={klineData}
              returnsCurve={returnsCurve}
              bhBenchmark={bhBenchmark}
              completedTrades={completedTrades}
              runBacktest={runBacktest}
              getSymbolStrategy={getSymbolStrategy}
              freq={freq}
            />
          )}

          {activeTab === 'report' && (
            <BatchReportView
              watchlist={watchlist}
              freq={freq}
              setFreq={setFreq}
            />
          )}

          {activeTab === 'optimizer' && (
            <OptimizerView
              watchlist={watchlist}
              strategies={strategies}
              paramsSchema={paramsSchema}
            />
          )}
        </main>
      </div>
    </ErrorBoundary>
  )
}
