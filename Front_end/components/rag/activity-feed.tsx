'use client'

import { MessageCircle, FileUp, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useRelativeTime } from '@/lib/hooks/use-rag'
import type { ActivityEvent } from '@/lib/models/types'
import { cn } from '@/lib/utils'

interface ActivityFeedProps {
  events: ActivityEvent[]
  isLoading?: boolean
  maxItems?: number
}

const eventIcons = {
  query: MessageCircle,
  ingestion: FileUp,
  error: AlertCircle,
}

const eventColors = {
  query: 'text-primary bg-primary/10',
  ingestion: 'text-success bg-success/10',
  error: 'text-destructive bg-destructive/10',
}

export function ActivityFeed({
  events,
  isLoading,
  maxItems = 10,
}: ActivityFeedProps) {
  const formatRelativeTime = useRelativeTime()
  const displayEvents = events.slice(0, maxItems)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-start gap-3">
                <Skeleton className="h-8 w-8 shrink-0 rounded-lg" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (displayEvents.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No recent activity</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {displayEvents.map((event) => {
            const Icon = eventIcons[event.type]
            const colorClass = eventColors[event.type]

            return (
              <div key={event.id} className="flex items-start gap-3">
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                    colorClass
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 space-y-0.5">
                  <p className="text-sm leading-tight">{event.description}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatRelativeTime(event.timestamp)}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
