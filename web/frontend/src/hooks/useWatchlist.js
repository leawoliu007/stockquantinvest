import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

export function useWatchlist(onSelectedChange) {
  const [watchlist, setWatchlist] = useState([])
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [quotes, setQuotes] = useState({})
  const [strategies, setStrategies] = useState([])
  const [paramsSchema, setParamsSchema] = useState({})

  const fetchQuotes = useCallback((items) => {
    if (!items || items.length === 0) return
    const symbols = items.map(i => i.symbol).join(",")
    axios.get(`${API}/quote`, { params: { symbols } })
      .then(r => {
        const quoteMap = {}
        for (const q of r.data) quoteMap[q.symbol] = q
        setQuotes(quoteMap)
      })
      .catch(() => {})
  }, [])

  const loadWatchlist = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/watchlist`)
      setWatchlist(res.data)
      if (res.data.length > 0 && !selectedSymbol) {
        const first = res.data[0].symbol
        setSelectedSymbol(first)
        onSelectedChange?.(first)
      }
      fetchQuotes(res.data)
    } catch {}
  }, [selectedSymbol, fetchQuotes, onSelectedChange])

  // Load strategies and params schema once
  useEffect(() => {
    axios.get(`${API}/strategies`).then(r => setStrategies(r.data)).catch(() => {})
    axios.get(`${API}/strategy-params-schema`).then(r => setParamsSchema(r.data)).catch(() => {})
  }, [])

  // Initial load
  useEffect(() => {
    loadWatchlist()
  }, [loadWatchlist])

  const changeStrategy = useCallback(async (symbol, newStrategy) => {
    try {
      await axios.patch(`${API}/watchlist/${symbol}`, { strategy: newStrategy })
      await axios.delete(`${API}/backtest-cached/${symbol}`)
      setWatchlist(prev => prev.map(w =>
        w.symbol === symbol ? { ...w, strategy: newStrategy } : w
      ))
    } catch {}
  }, [])

  const addSymbol = useCallback(async (symbol, name = '') => {
    if (!symbol) return
    try {
      await axios.post(`${API}/watchlist`, { symbol, name, market: '' })
      await loadWatchlist()
    } catch {}
  }, [loadWatchlist])

  const removeSymbol = useCallback(async (symbol) => {
    try {
      await axios.delete(`${API}/watchlist/${symbol}`)
      const res = await axios.get(`${API}/watchlist`)
      setWatchlist(res.data)
      if (selectedSymbol === symbol) {
        const next = res.data.length > 0 ? res.data[0].symbol : null
        setSelectedSymbol(next)
        onSelectedChange?.(next)
        fetchQuotes(res.data)
      }
    } catch {}
  }, [selectedSymbol, onSelectedChange, fetchQuotes])

  const getSymbolStrategy = useCallback((sym) => {
    const item = watchlist.find(w => w.symbol === sym)
    return item?.strategy || 'macross'
  }, [watchlist])

  const updateSymbolParams = useCallback(async (symbol, strategy, params) => {
    try {
      await axios.patch(`${API}/watchlist/${symbol}`, {
        strategy,
        strategy_params: params,
      })
      setWatchlist(prev => prev.map(w =>
        w.symbol === symbol ? { ...w, strategy_params: { ...params } } : w
      ))
      await axios.delete(`${API}/backtest-cached/${symbol}`)
    } catch {}
  }, [])

  return {
    watchlist,
    selectedSymbol,
    setSelectedSymbol,
    quotes,
    strategies,
    paramsSchema,
    loadWatchlist,
    changeStrategy,
    addSymbol,
    removeSymbol,
    getSymbolStrategy,
    updateSymbolParams,
  }
}
