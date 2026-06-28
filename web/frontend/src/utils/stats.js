/**
 * Calculate trading statistics from completed trades array.
 * Shared by both cached and fresh backtest paths to eliminate duplication.
 */
export function calculateStats(trades, extra = {}) {
  const wins = trades.filter(t => t.is_profitable)
  const losses = trades.filter(t => !t.is_profitable)
  const winRate = trades.length > 0 ? (wins.length / trades.length * 100) : 0
  const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.pnl, 0) / losses.length) : 1
  const plRatio = avgLoss > 0 ? (avgWin / avgLoss) : 0
  const avgPositiveReturn = wins.length > 0
    ? wins.reduce((s, t) => s + ((t.sell_price - t.buy_price) / t.buy_price * 100), 0) / wins.length : 0
  const avgNegativeReturn = losses.length > 0
    ? losses.reduce((s, t) => s + ((t.sell_price - t.buy_price) / t.buy_price * 100), 0) / losses.length : 0

  return {
    finalValue: extra.final_value ?? 0,
    totalReturn: extra.total_return_pct ?? 0,
    bars: extra.bars ?? 0,
    trades: trades.length,
    winCount: wins.length,
    lossCount: losses.length,
    winRate,
    plRatio,
    avgPositiveReturn,
    avgNegativeReturn,
  }
}

/**
 * Regenerate buy-and-hold benchmark from kline data.
 */
export function calculateBuyHoldBenchmark(kline) {
  if (!kline || kline.length === 0) return []
  const firstPrice = kline[0].close
  return kline.map(r => ({
    date: r.date,
    value: +((r.close - firstPrice) / firstPrice * 100).toFixed(2),
  }))
}

/**
 * Format strategy params object to readable string.
 */
export function formatParams(params) {
  return Object.entries(params).map(([k, v]) => `${k}=${v}`).join(', ')
}
