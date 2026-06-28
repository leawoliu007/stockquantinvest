import { useState, useCallback, useRef, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

export function useSymbolResolver() {
  const [resolvedSymbol, setResolvedSymbol] = useState(null)
  const [resolvedName, setResolvedName] = useState(null)
  const [resolving, setResolving] = useState(false)
  const [resolveError, setResolveError] = useState(null)
  const [ambiguousModal, setAmbiguousModal] = useState(null)
  const resolveTimer = useRef(null)

  useEffect(() => {
    return () => {
      if (resolveTimer.current) clearTimeout(resolveTimer.current)
    }
  }, [])

  const resolveCode = useCallback((code) => {
    code = code.trim()
    if (!code || code.includes(".")) {
      setResolvedSymbol(code || null)
      setResolvedName(null)
      setResolveError(null)
      return
    }
    if (resolveTimer.current) clearTimeout(resolveTimer.current)
    setResolving(true)
    setResolveError(null)
    resolveTimer.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/resolve-symbol`, { params: { code } })
        if (res.data.ambiguous && res.data.alternatives && res.data.alternatives.length > 1) {
          setAmbiguousModal({
            code,
            alternatives: res.data.alternatives,
            selected: res.data.symbol,
            name: res.data.name || '',
          })
          setResolvedSymbol(null)
          setResolvedName(null)
        } else {
          setResolvedSymbol(res.data.symbol)
          setResolvedName(res.data.name || null)
        }
      } catch (e) {
        setResolveError(e.response?.data?.detail || "未找到")
        setResolvedSymbol(null)
        setResolvedName(null)
      } finally {
        setResolving(false)
      }
    }, 500)
  }, [])

  const dismissAmbiguous = useCallback(() => setAmbiguousModal(null), [])

  return {
    resolvedSymbol,
    resolvedName,
    resolving,
    resolveError,
    ambiguousModal,
    resolveCode,
    dismissAmbiguous,
  }
}
