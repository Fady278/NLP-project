'use client'

import { useEffect, useState } from 'react'

import { API_CONFIG, getMockMode, setMockMode } from '@/lib/config/api'

export function useMockMode() {
  const [mockMode, setMockModeState] = useState<boolean>(API_CONFIG.defaultMockMode)

  useEffect(() => {
    const sync = () => setMockModeState(getMockMode())
    sync()
    window.addEventListener('storage', sync)
    window.addEventListener('rag-console-mock-mode-change', sync as EventListener)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener('rag-console-mock-mode-change', sync as EventListener)
    }
  }, [])

  return {
    mockMode,
    setMockMode: (value: boolean) => {
      setMockMode(value)
      setMockModeState(value)
    },
  }
}
