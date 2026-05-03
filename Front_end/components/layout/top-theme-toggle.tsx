'use client'

import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/components/theme-provider'

export function TopThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const isDark = mounted && resolvedTheme === 'dark'

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="gap-2 rounded-xl border-border/60 bg-background/65 px-3 text-xs font-medium shadow-sm backdrop-blur-sm"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label="Toggle theme"
    >
      <span className="relative flex h-4 w-4 items-center justify-center">
        <Sun className={`absolute h-4 w-4 transition-all ${isDark ? 'rotate-90 scale-0' : 'rotate-0 scale-100 text-warning'}`} />
        <Moon className={`absolute h-4 w-4 transition-all ${isDark ? 'rotate-0 scale-100 text-primary' : '-rotate-90 scale-0'}`} />
      </span>
      <span>{isDark ? 'Dark' : 'Light'}</span>
    </Button>
  )
}
