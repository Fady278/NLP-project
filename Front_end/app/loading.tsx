'use client'

import { BrainCircuit } from 'lucide-react'

export default function Loading() {
  return (
    <div className="flex h-full min-h-[50vh] w-full flex-col items-center justify-center gap-4">
      <div className="relative flex h-16 w-16 items-center justify-center">
        <div className="absolute inset-0 animate-ping rounded-xl bg-primary/20" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-primary/90 to-accent/60 shadow-lg shadow-primary/20">
          <BrainCircuit className="h-8 w-8 animate-pulse text-primary-foreground" />
        </div>
      </div>
      <div className="space-y-1 text-center">
        <h3 className="text-lg font-semibold tracking-tight text-foreground">Loading Module</h3>
        <p className="text-sm text-muted-foreground">Please wait while the page is prepared...</p>
      </div>
    </div>
  )
}
