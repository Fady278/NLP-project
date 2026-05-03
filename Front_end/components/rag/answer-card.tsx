'use client'

import { MessageCircle, ChevronRight, FileText } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useRelativeTime } from '@/lib/hooks/use-rag'
import type { QueryAnswer } from '@/lib/models/types'
import { cn } from '@/lib/utils'

interface AnswerCardProps {
  answer: QueryAnswer
  isSelected?: boolean
  onClick?: () => void
}

export function AnswerCard({ answer, isSelected, onClick }: AnswerCardProps) {
  const formatRelativeTime = useRelativeTime()

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all hover:border-primary/50',
        isSelected && 'border-primary ring-1 ring-primary/20'
      )}
      onClick={onClick}
    >
      <CardContent className="p-4">
        {/* Question */}
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <MessageCircle className="h-4 w-4 text-primary" />
          </div>
          <div className="flex-1 space-y-1">
            <p className="font-medium leading-tight">{answer.question}</p>
            <p className="text-xs text-muted-foreground">
              {formatRelativeTime(answer.timestamp)}
            </p>
          </div>
        </div>

        {/* Answer */}
        <div className="mt-4 rounded-lg bg-muted/50 p-3">
          <p className="text-sm leading-relaxed text-foreground/90">
            {answer.answer}
          </p>
        </div>

        {/* Footer */}
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="gap-1">
              <FileText className="h-3 w-3" />
              {answer.chunks.length} sources
            </Badge>
            {answer.modelUsed && (
              <span className="hidden sm:inline">{answer.modelUsed}</span>
            )}
          </div>
          <div className="flex items-center gap-1 text-primary">
            <span>View evidence</span>
            <ChevronRight className="h-3 w-3" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
