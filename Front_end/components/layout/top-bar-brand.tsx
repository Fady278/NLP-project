'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTheme } from 'next-themes'
import { useSidebar } from '@/components/ui/sidebar'

export function TopBarBrand() {
  const { state, isMobile } = useSidebar()
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const shouldShowBrand = mounted && (isMobile || state === 'collapsed')
  const detectiveIcon =
    mounted && resolvedTheme === 'dark'
      ? '/detective-icon-dark.png'
      : '/detective-icon-light.png'

  if (!shouldShowBrand) {
    return <span className="text-sm font-medium text-muted-foreground">RAG Console</span>
  }

  return (
    <Link href="/" className="flex items-center gap-2.5">
      <div className="overflow-hidden rounded-xl border border-border/60 bg-card/90 p-0.5 shadow-sm">
        <Image
          src={detectiveIcon}
          alt="RAG Console"
          width={30}
          height={30}
          className="h-7 w-7 object-cover"
          priority
        />
      </div>
      <span className="text-sm font-medium text-muted-foreground">RAG Console</span>
    </Link>
  )
}
