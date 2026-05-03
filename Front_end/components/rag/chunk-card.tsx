'use client'

import { useState } from 'react'
import { FileText, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { RetrievedChunk } from '@/lib/models/types'
import { cn } from '@/lib/utils'

interface ChunkCardProps {
  chunk: RetrievedChunk
  rank: number
}

export function ChunkCard({ chunk, rank }: ChunkCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const scoreColor =
    chunk.score >= 0.8
      ? 'bg-success/10 text-success'
      : chunk.score >= 0.6
        ? 'bg-warning/10 text-warning-foreground'
        : 'bg-muted text-muted-foreground'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(chunk.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const displayText = isExpanded
    ? chunk.text
    : chunk.text.length > 200
      ? chunk.text.slice(0, 200) + '...'
      : chunk.text

  return (
    <Card>
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              {rank}
            </span>
            <div className="flex items-center gap-1.5 text-sm">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-medium">{chunk.source}</span>
            </div>
          </div>
          <Badge variant="secondary" className={cn('text-xs', scoreColor)}>
            {(chunk.score * 100).toFixed(0)}%
          </Badge>
        </div>

        {/* Metadata */}
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
          {chunk.pageNumber && <span>Page {chunk.pageNumber}</span>}
          {chunk.section && (
            <>
              {chunk.pageNumber && <span>•</span>}
              <span>{chunk.section}</span>
            </>
          )}
        </div>

        {/* Text */}
        <div className="mt-3 rounded-md bg-muted/30 p-3">
          <p className="whitespace-pre-wrap font-mono text-xs leading-relaxed">
            {displayText}
          </p>
        </div>

        {/* Actions */}
        <div className="mt-3 flex items-center justify-between">
          {chunk.text.length > 200 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="mr-1 h-3 w-3" />
                  Show less
                </>
              ) : (
                <>
                  <ChevronDown className="mr-1 h-3 w-3" />
                  Show more
                </>
              )}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto h-7 px-2 text-xs"
            onClick={handleCopy}
          >
            {copied ? (
              <>
                <Check className="mr-1 h-3 w-3" />
                Copied
              </>
            ) : (
              <>
                <Copy className="mr-1 h-3 w-3" />
                Copy
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
