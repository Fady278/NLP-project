'use client'

import * as React from 'react'

type Theme = 'light' | 'dark' | 'system'

export interface ThemeProviderProps {
  children: React.ReactNode
  attribute?: 'class'
  defaultTheme?: Theme
  enableSystem?: boolean
  disableTransitionOnChange?: boolean
}

interface ThemeContextValue {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
}

const THEME_STORAGE_KEY = 'rag-console-theme'

const ThemeContext = React.createContext<ThemeContextValue | undefined>(undefined)

function resolveTheme(theme: Theme, enableSystem: boolean): 'light' | 'dark' {
  if (theme === 'system' && enableSystem && typeof window !== 'undefined') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return theme === 'dark' ? 'dark' : 'light'
}

function applyTheme(resolvedTheme: 'light' | 'dark', disableTransitionOnChange: boolean): void {
  const root = document.documentElement

  if (disableTransitionOnChange) {
    root.classList.add('[&_*]:!transition-none')
    window.setTimeout(() => {
      root.classList.remove('[&_*]:!transition-none')
    }, 0)
  }

  root.classList.remove('light', 'dark')
  root.classList.add(resolvedTheme)
  root.style.colorScheme = resolvedTheme
}

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  enableSystem = true,
  disableTransitionOnChange = false,
}: ThemeProviderProps) {
  const [theme, setThemeState] = React.useState<Theme>(defaultTheme)
  const [resolvedTheme, setResolvedTheme] = React.useState<'light' | 'dark'>(
    defaultTheme === 'dark' ? 'dark' : 'light'
  )

  React.useEffect(() => {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    const initialTheme: Theme =
      storedTheme === 'light' || storedTheme === 'dark' || storedTheme === 'system'
        ? storedTheme
        : defaultTheme

    const apply = (nextTheme: Theme) => {
      const nextResolved = resolveTheme(nextTheme, enableSystem)
      setThemeState(nextTheme)
      setResolvedTheme(nextResolved)
      applyTheme(nextResolved, disableTransitionOnChange)
    }

    apply(initialTheme)

    if (!enableSystem) {
      return
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => {
      const currentTheme = window.localStorage.getItem(THEME_STORAGE_KEY) as Theme | null
      const activeTheme = currentTheme || initialTheme
      if (activeTheme === 'system') {
        apply('system')
      }
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [defaultTheme, enableSystem, disableTransitionOnChange])

  const setTheme = React.useCallback(
    (nextTheme: Theme) => {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
      const nextResolved = resolveTheme(nextTheme, enableSystem)
      setThemeState(nextTheme)
      setResolvedTheme(nextResolved)
      applyTheme(nextResolved, disableTransitionOnChange)
    },
    [enableSystem, disableTransitionOnChange]
  )

  const value = React.useMemo<ThemeContextValue>(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
    }),
    [theme, resolvedTheme, setTheme]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = React.useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
