'use client'

import { FileText, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ChunkCard } from './chunk-card'
import type { QueryAnswer } from '@/lib/models/types'

interface EvidencePanelProps {
  answer: QueryAnswer
  onClose: () => void
}

export function EvidencePanel({ answer, onClose }: EvidencePanelProps) {
  return (
    <div className="flex h-full flex-col rounded-lg border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-medium">Evidence Sources</h3>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs">
            {answer.chunks.length}
          </span>
        </div>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onClose}>
          <X className="h-4 w-4" />
          <span className="sr-only">Close panel</span>
        </Button>
      </div>

      {/* Question context */}
      <div className="border-b bg-muted/30 px-4 py-3">
        <p className="text-xs text-muted-foreground">Evidence for:</p>
        <p className="mt-1 text-sm font-medium">{answer.question}</p>
      </div>

      {/* Chunks */}
      <ScrollArea className="flex-1">
        <div className="space-y-3 p-4">
          {answer.chunks.map((chunk, index) => (
            <ChunkCard key={chunk.id} chunk={chunk} rank={index + 1} />
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
