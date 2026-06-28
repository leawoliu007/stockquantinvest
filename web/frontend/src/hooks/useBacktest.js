import { useState, useCallback, useRef, useEffect } from 'react'
import axios from 'axios'
import { calculateStats, calculateBuyHoldBenchmark } from '../utils/stats'

const API = '/api'

export function useBacktest(selectedSymbol, freq, getSymbolStrategy) {
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [klineData, setKlineData] = useState([])
  const [returnsCurve, setReturnsCurve] = useState([])
  const [bhBenchmark, setBhBenchmark] = useState([])
  const [signals, setSignals] = useState([])
  const [positionMap, setPositionMap] = useState({})
  const [completedTrades, setCompletedTrades] = useState([])
  const [stats, setStats] = useState(null)

  const reqSeq = useRef(0)
  const debounceTimer = useRef(null)
  const lastLoadKey = useRef(null)

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [])

  const clearResults = useCallback(() => {
    setKlineData([])
    setReturnsCurve([])
    setBhBenchmark([])
    setSignals([])
    setPositionMap({})
    setCompletedTrades([])
    setStats(null)
  }, [])

  const populateFromFresh = useCallback((res) => {
    const trades = res.data.completed_trades || []
    setKlineData(res.data.kline || [])
    setReturnsCurve(res.data.returns_curve || [])
    setBhBenchmark(res.data.bh_benchmark || [])
    setSignals(res.data.signals || [])
    setPositionMap(res.data.position_map || {})
    setCompletedTrades(trades)
    setStats(calculateStats(trades, {
      final_value: res.data.final_value,
      total_return_pct: res.data.total_return_pct,
      bars: res.data.bars,
    }))
  }, [])

  const runBacktest = useCallback(async () => {
    if (!selectedSymbol) return
    const seq = ++reqSeq.current
    setRunning(true)
    try {
      const res = await axios.get(`${API}/analyze`, {
        params: { symbol: selectedSymbol, freq },
      })
      if (seq !== reqSeq.current) return // stale
      populateFromFresh(res)
    } catch (e) {
      if (seq !== reqSeq.current) return
      if (e.name === 'CanceledError') return
      console.error('Backtest failed:', e)
      clearResults()
    } finally {
      setRunning(false)
    }
  }, [selectedSymbol, freq, populateFromFresh, clearResults])

  const loadCachedBacktest = useCallback(async () => {
    if (!selectedSymbol) return
    if (loading || running) return
    const strategy = getSymbolStrategy(selectedSymbol)
    setLoading(true)
    try {
      const res = await axios.get(`${API}/backtest-cached/${selectedSymbol}`, {
        params: { freq, strategy },
      })
      if (res.data) {
        const cached = res.data
        const kline = cached.kline || []
        setKlineData(kline)
        setReturnsCurve(cached.returns_curve || [])
        setBhBenchmark(calculateBuyHoldBenchmark(kline))
        setSignals([])
        setPositionMap({})
        const trades = cached.trades || []
        setCompletedTrades(trades)
        setStats(calculateStats(trades, {
          final_value: cached.final_value,
          total_return_pct: cached.total_return_pct,
          bars: kline.length,
          trade_count: cached.trade_count,
          win_count: cached.win_count,
          loss_count: cached.loss_count,
          pl_ratio: cached.pl_ratio || 0,
          avg_positive_return: cached.avg_positive_return || 0,
          avg_negative_return: cached.avg_negative_return || 0,
        }))
        setLoading(false)
        return
      }
    } catch {}
    setLoading(false)
    runBacktest()
  }, [selectedSymbol, freq, loading, running, getSymbolStrategy, runBacktest])

  // Auto-load when symbol/freq/strategy changes (debounced)
  useEffect(() => {
    if (!selectedSymbol) return
    const strategy = getSymbolStrategy(selectedSymbol)
    const key = `${selectedSymbol}:${freq}:${strategy}`
    if (lastLoadKey.current === key) return
    lastLoadKey.current = key
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(loadCachedBacktest, 200)
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [selectedSymbol, freq, getSymbolStrategy, loadCachedBacktest])

  return {
    loading,
    running,
    klineData,
    returnsCurve,
    bhBenchmark,
    signals,
    positionMap,
    completedTrades,
    stats,
    runBacktest,
  }
}
