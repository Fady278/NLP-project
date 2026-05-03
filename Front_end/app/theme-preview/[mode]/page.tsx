'use client'

import { useEffect } from 'react'
import { useParams, useSearchParams } from 'next/navigation'

type ThemeMode = 'light' | 'dark'

function normalizeMode(value: string | string[] | undefined): ThemeMode {
  return value === 'dark' ? 'dark' : 'light'
}

export default function ThemePreviewPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const mode = normalizeMode(params.mode)
  const nextPath = searchParams.get('next') || '/'

  useEffect(() => {
    window.localStorage.setItem('rag-console-theme', mode)
    document.documentElement.classList.remove('light', 'dark')
    document.documentElement.classList.add(mode)
    document.documentElement.style.colorScheme = mode
    window.location.replace(nextPath)
  }, [mode, nextPath])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background text-foreground">
      <div className="surface max-w-md rounded-2xl px-6 py-5 text-center">
        <p className="label-caps">Theme Preview</p>
        <h1 className="mt-3 text-xl font-bold tracking-tight">Applying {mode} mode</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Redirecting to <span className="font-medium text-foreground">{nextPath}</span>
        </p>
      </div>
    </div>
  )
}
