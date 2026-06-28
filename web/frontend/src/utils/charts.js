/**
 * Build ECharts option for K-line chart with MA34, chip cost curves, and volume.
 */
export function createKlineOption(kline, completedTrades) {
  const clean = kline.filter(d => d.open > 0 && d.close > 0 && d.high > 0 && d.low > 0)
  const dates = clean.map(d => d.date)
  const ohlc = clean.map(d => [d.open, d.close, d.low, d.high])
  const volumes = clean.map(d => d.volume)

  // MA34
  const sma34 = clean.map((_, i) => {
    if (i < 33) return null
    let sum = 0
    for (let j = i - 33; j <= i; j++) sum += clean[j].close
    return +(sum / 34).toFixed(2)
  })

  // Chip cost curves
  const { cost20, cost50, cost80 } = computeChipCosts(clean)

  // Mark area for trades
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
        itemStyle: { color: '#10b981', color0: '#ef4444', borderColor: '#10b981', borderColor0: '#ef4444' },
        markArea: { silent: true, itemStyle: { borderWidth: 0 }, data: markAreaData },
      },
      { name: 'MA34', type: 'line', data: sma34, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#a78bfa' } },
      { name: '筹码20%', type: 'line', data: cost20, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: 'rgba(16,185,129,0.8)' } },
      { name: '筹码50%', type: 'line', data: cost50, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: 'rgba(245,158,11,0.8)' } },
      { name: '筹码80%', type: 'line', data: cost80, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: 'rgba(239,68,68,0.8)' } },
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

function computeChipCosts(clean) {
  const prices = clean.map(d => d.close)
  const minP = Math.min(...prices) * 0.95
  const maxP = Math.max(...prices) * 1.05
  const binWidth = (maxP - minP) / 200
  const numBins = 200
  const decay = Math.pow(0.5, 1 / 60)

  let chips = new Array(numBins).fill(0)
  const cost20 = new Array(clean.length).fill(null)
  const cost50 = new Array(clean.length).fill(null)
  const cost80 = new Array(clean.length).fill(null)

  const priceToBin = (p) => Math.min(numBins - 1, Math.max(0, Math.floor((p - minP) / binWidth)))

  for (let i = 0; i < clean.length; i++) {
    const d = clean[i]
    const vol = d.volume || 0

    for (let b = 0; b < numBins; b++) chips[b] *= decay

    const centerBin = priceToBin(d.close)
    const spread = Math.max(2, Math.floor(0.015 * (maxP - minP) / binWidth))
    for (let offset = -spread; offset <= spread; offset++) {
      const bin = centerBin + offset
      if (bin >= 0 && bin < numBins) {
        const weight = Math.exp(-(offset * offset) / (2 * spread * 0.3))
        chips[bin] += vol * weight
      }
    }

    let totalChips = chips.reduce((s, v) => s + v, 0)
    if (totalChips === 0) continue

    let cumChips = 0
    for (let b = 0; b < numBins; b++) {
      cumChips += chips[b]
      const cumPct = cumChips / totalChips * 100
      const binPrice = minP + (b + 0.5) * binWidth
      if (cumPct >= 20 && cost20[i] === null) cost20[i] = +(binPrice).toFixed(2)
      if (cumPct >= 50 && cost50[i] === null) cost50[i] = +(binPrice).toFixed(2)
      if (cumPct >= 80 && cost80[i] === null) cost80[i] = +(binPrice).toFixed(2)
    }

    if (i > 0) {
      if (cost20[i] === null) cost20[i] = cost20[i - 1]
      if (cost50[i] === null) cost50[i] = cost50[i - 1]
      if (cost80[i] === null) cost80[i] = cost80[i - 1]
    }
  }

  return { cost20, cost50, cost80 }
}

/**
 * Build ECharts option for returns curve chart.
 */
export function createReturnsOption(returns, benchmark, completedTrades, klineDates) {
  const dates = klineDates || returns.map(d => d.date)

  const retMap = {}
  for (const r of returns) retMap[r.date] = r.value
  const bhMap = {}
  for (const b of benchmark) bhMap[b.date] = b.value

  let lastRet = null
  let lastBh = null
  const strategyValues = dates.map(d => { retMap[d] !== undefined && (lastRet = retMap[d]); return lastRet })
  const bhValues = dates.map(d => { bhMap[d] !== undefined && (lastBh = bhMap[d]); return lastBh })

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
    legend: { data: ['策略收益率', '持有基准'], textStyle: { color: '#9ca3af' }, top: 0 },
    grid: { left: 60, right: 20, top: 30, bottom: 5 },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { show: false } },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } },
      axisLabel: { color: '#9ca3af', fontSize: 10, formatter: (v) => `${v >= 0 ? '+' : ''}${v}%` },
    },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
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
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.08)' },
              { offset: 1, color: 'rgba(59,130,246,0.01)' },
            ],
          },
        },
        markArea: { silent: true, itemStyle: { borderWidth: 0 }, data: markAreaData },
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
