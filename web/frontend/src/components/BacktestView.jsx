import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { createKlineOption, createReturnsOption } from '../utils/charts'

export function BacktestView({
  selectedSymbol, loading, running, stats, klineData, returnsCurve, bhBenchmark,
  completedTrades, runBacktest, getSymbolStrategy, freq,
}) {
  const cleanDates = useMemo(
    () => klineData.filter(d => d.open > 0 && d.close > 0 && d.high > 0 && d.low > 0).map(d => d.date),
    [klineData]
  )

  const klineOption = useMemo(
    () => createKlineOption(klineData, completedTrades),
    [klineData, completedTrades]
  )

  const returnsOption = useMemo(
    () => createReturnsOption(returnsCurve, bhBenchmark, completedTrades, cleanDates),
    [returnsCurve, bhBenchmark, completedTrades, cleanDates]
  )

  return (
    <>
      <header className="main-header">
        <h2>{selectedSymbol || '选择股票'}</h2>
        <button className="run-btn" onClick={runBacktest} disabled={loading || running}>
          {loading ? '加载中...' : running ? '回测中...' : '运行回测'}
        </button>
      </header>

      {stats && <StatsCards stats={stats} />}

      <div className="charts-container">
        {klineData.length > 0 ? (
          <>
            <div className="chart-panel kline">
              <ReactECharts
                option={klineOption}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
              />
            </div>
            <div className="chart-panel equity">
              <ReactECharts
                option={returnsOption}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
              />
            </div>
            {completedTrades.length > 0 && <TradesTable trades={completedTrades} />}
          </>
        ) : (
          <div className="placeholder">
            {loading ? <><span className="loading-spinner" /> 加载中...</> :
             running ? <><span className="loading-spinner" /> 回测中...</> :
             '选择股票开始回测'}
          </div>
        )}
      </div>
    </>
  )
}

/* --- Stats Cards --- */

function StatsCards({ stats }) {
  return (
    <div className="stats-row">
      <div className="stat-card multi-col">
        <StatCol label="总收益率" value={`${stats.totalReturn >= 0 ? '+' : ''}${stats.totalReturn}%`} className={stats.totalReturn >= 0 ? 'positive' : 'negative'} />
        <StatCol label="均盈" value={`+${stats.avgPositiveReturn.toFixed(2)}%`} className="positive" />
        <StatCol label="均亏" value={`${stats.avgNegativeReturn.toFixed(2)}%`} className="negative" />
      </div>
      <div className="stat-card multi-col">
        <StatCol label="交易次数" value={stats.trades} />
        <StatCol label="盈利" value={stats.winCount} className="positive" />
        <StatCol label="亏损" value={stats.lossCount} className="negative" />
      </div>
      <div className="stat-card multi-col">
        <StatCol label="胜率" value={`${stats.winRate.toFixed(1)}%`} className={stats.winRate >= 50 ? 'positive' : 'negative'} />
        <StatCol label="盈亏比" value={`${stats.plRatio.toFixed(2)}`} className={stats.plRatio >= 1 ? 'positive' : 'negative'} />
        <StatCol label="K线数" value={stats.bars} />
      </div>
    </div>
  )
}

function StatCol({ label, value, className }) {
  return (
    <div className="stat-col">
      <div className="label">{label}</div>
      <div className={`value ${className || ''}`}>{value}</div>
    </div>
  )
}

/* --- Trades Table --- */

function TradesTable({ trades }) {
  return (
    <div className="trades-table-wrapper">
      <table className="trades-table">
        <thead>
          <tr><th>买入日期</th><th>卖出日期</th><th>买入价</th><th>卖出价</th><th>收益</th></tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
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
  )
}
