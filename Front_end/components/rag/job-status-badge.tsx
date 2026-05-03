import { Clock, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { IngestionStatus } from '@/lib/models/types'
import { cn } from '@/lib/utils'

interface JobStatusBadgeProps {
  status: IngestionStatus
  className?: string
}

const statusConfig = {
  queued: {
    label: 'Queued',
    icon: Clock,
    className: 'bg-muted text-muted-foreground',
  },
  processing: {
    label: 'Processing',
    icon: Loader2,
    className: 'bg-warning/10 text-warning-foreground',
    animate: true,
  },
  indexed: {
    label: 'Indexed',
    icon: CheckCircle2,
    className: 'bg-success/10 text-success',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    className: 'bg-destructive/10 text-destructive',
  },
}

export function JobStatusBadge({ status, className }: JobStatusBadgeProps) {
  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <Badge
      variant="secondary"
      className={cn('gap-1.5', config.className, className)}
    >
      <Icon
        className={cn('h-3 w-3', 'animate' in config && config.animate && 'animate-spin')}
      />
      {config.label}
    </Badge>
  )
}
