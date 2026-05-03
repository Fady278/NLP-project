'use client'

import Link from 'next/link'
import {
  FileText,
  Layers,
  Activity,
  Clock,
  MessageCircleQuestion,
  FileUp,
  Search,
  ArrowRight,
  Zap,
  BrainCircuit,
  Database,
  Cpu,
  Users,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FadeIn, StaggerContainer, StaggerItem } from '@/components/ui/fade-in'
import { setPendingChatQuestion } from '@/lib/config/api'
import { useStats, useActivity, useRelativeTime } from '@/lib/hooks/use-rag'
import { useMockMode } from '@/lib/hooks/use-api-mode'

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useStats()
  const { data: activity, isLoading: activityLoading } = useActivity()
  const formatRelativeTime = useRelativeTime()
  const { mockMode } = useMockMode()

  const healthStatus = {
    healthy: { label: 'Healthy', color: 'bg-success', textColor: 'text-success' },
    degraded: { label: 'Degraded', color: 'bg-warning', textColor: 'text-warning' },
    offline: { label: 'Offline', color: 'bg-destructive', textColor: 'text-destructive' },
  }

  const currentHealth = stats?.retrievalHealth
    ? healthStatus[stats.retrievalHealth]
    : healthStatus.healthy

  const getActivityHref = (event: { type: string }) => (event.type === 'ingestion' ? '/ingest' : '/ask')
  const getActivityQuestion = (description: string) => description.match(/^Query:\s*"(.*)"$/)?.[1]?.trim() || ''

  return (
    <div className="min-h-full px-6 py-10">
      <div className="mx-auto max-w-6xl space-y-10">

        {/* ─── Hero ─── */}
        <FadeIn direction="up" delay={0.1}>
          <section className="relative overflow-hidden rounded-2xl surface p-10">
            {/* Floating orbs */}
            <div className="orb orb-amber" style={{ width: 220, height: 220, top: -60, right: -40 }} />
            <div className="orb orb-teal" style={{ width: 160, height: 160, bottom: -40, left: '20%' }} />
            <div className="orb orb-rose" style={{ width: 120, height: 120, top: '30%', right: '30%' }} />

            <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-lg">
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                  <BrainCircuit className="h-3.5 w-3.5" />
                  Knowledge Engine
                </div>
                <h1 className="mt-4 text-3xl font-bold tracking-tight lg:text-4xl">
                  Your knowledge,{' '}
                  <span className="text-gradient">instantly searchable</span>
                </h1>
                <p className="mt-3 text-base text-muted-foreground leading-relaxed">
                  Ingest documents, ask questions in natural language, and get precise answers backed by evidence from your own data.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button size="lg" className="btn-glow group gap-2.5 rounded-xl px-6 text-sm font-semibold" asChild>
                  <Link href="/ask">
                    <MessageCircleQuestion className="h-4.5 w-4.5" />
                    Ask AI
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" className="gap-2 rounded-xl border-border/60 bg-background/50 transition-colors hover:border-primary/40 hover:bg-primary/5" asChild>
                  <Link href="/ingest">
                    <FileUp className="h-4.5 w-4.5" />
                    Upload
                  </Link>
                </Button>
                <Button size="lg" variant="outline" className="gap-2 rounded-xl border-border/60 bg-background/50 transition-colors hover:border-accent/40 hover:bg-accent/5" asChild>
                  <Link href="/retrieval">
                    <Search className="h-4.5 w-4.5" />
                    Browse
                  </Link>
                </Button>
              </div>
            </div>
          </section>
        </FadeIn>

        {/* ─── Stats ─── */}
        <StaggerContainer className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Indexed Documents */}
          <StaggerItem className="surface-raised animated-border group p-5">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <FileText className="h-4.5 w-4.5 text-primary" />
              </div>
              <span className="label-caps">Documents</span>
            </div>
            <p className="mt-5 text-3xl font-bold stat-number">
              {statsLoading ? (
                <span className="inline-block h-9 w-14 animate-pulse rounded-md bg-muted" />
              ) : (
                stats?.totalDocuments ?? 0
              )}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">Indexed &amp; searchable</p>
          </StaggerItem>

          {/* Total Chunks */}
          <StaggerItem className="surface-raised animated-border group p-5">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10">
                <Layers className="h-4.5 w-4.5 text-accent" />
              </div>
              <span className="chip">
                <Zap className="h-3 w-3 text-success" /> Live
              </span>
            </div>
            <p className="mt-5 text-3xl font-bold stat-number">
              {statsLoading ? (
                <span className="inline-block h-9 w-14 animate-pulse rounded-md bg-muted" />
              ) : (
                (stats?.totalChunks ?? 0).toLocaleString()
              )}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">Total chunks in store</p>
          </StaggerItem>

          {/* Retrieval Health */}
          <StaggerItem className="surface-raised animated-border group p-5">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-chart-3/10">
                <Cpu className="h-4.5 w-4.5 text-chart-3" />
              </div>
              <div className={`status-dot ${currentHealth.color === 'bg-success' ? 'status-dot--ok' : 'status-dot--warn'}`} />
            </div>
            <p className={`mt-5 text-3xl font-bold stat-number ${currentHealth.textColor}`}>
              {statsLoading ? (
                <span className="inline-block h-9 w-16 animate-pulse rounded-md bg-muted" />
              ) : (
                currentHealth.label
              )}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {stats?.avgRetrievalLatencyMs ? `${stats.avgRetrievalLatencyMs}ms avg` : 'System Status'}
            </p>
          </StaggerItem>

          {/* Last Ingestion */}
          <StaggerItem className="surface-raised animated-border group p-5">
            <div className="flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-chart-4/10">
                <Clock className="h-4.5 w-4.5 text-chart-4" />
              </div>
              <span className="label-caps">Recent</span>
            </div>
            <p className="mt-5 text-3xl font-bold stat-number">
              {statsLoading ? (
                <span className="inline-block h-9 w-20 animate-pulse rounded-md bg-muted" />
              ) : stats?.lastIngestionAt ? (
                formatRelativeTime(new Date(stats.lastIngestionAt))
              ) : (
                'Never'
              )}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">Last ingestion</p>
          </StaggerItem>
        </StaggerContainer>

        {/* ─── Activity & Sidebar ─── */}
        <StaggerContainer className="grid gap-6 lg:grid-cols-5">
          {/* Activity Feed */}
          <StaggerItem className="lg:col-span-3 surface overflow-hidden">
            <div className="flex items-center justify-between border-b border-border/40 px-6 py-4">
              <div className="flex items-center gap-3">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Recent Activity</h2>
                <span className="flex items-center gap-1.5 chip">
                  <span className="status-dot status-dot--ok" style={{ width: 6, height: 6 }} />
                  Live
                </span>
              </div>
            </div>

            <div className="divide-y divide-border/30">
              {activityLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4 px-6 py-4">
                    <div className="h-9 w-9 animate-pulse rounded-lg bg-muted" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-48 animate-pulse rounded bg-muted" />
                      <div className="h-3 w-24 animate-pulse rounded bg-muted" />
                    </div>
                  </div>
                ))
              ) : activity && activity.length > 0 ? (
                activity.slice(0, 6).map((event, i) => (
                  <Link
                    key={i}
                    href={getActivityHref(event)}
                    onClick={() => {
                      const question = getActivityQuestion(event.description)
                      if (question) {
                        setPendingChatQuestion(question)
                      }
                    }}
                    className="group flex items-center gap-4 px-6 py-4 transition-colors hover:bg-muted/20"
                  >
                    <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${event.type === 'query' ? 'bg-primary/10 text-primary' :
                        event.type === 'ingestion' ? 'bg-accent/10 text-accent' :
                          'bg-destructive/10 text-destructive'
                      }`}>
                      {event.type === 'query' ? (
                        <MessageCircleQuestion className="h-4 w-4" />
                      ) : event.type === 'ingestion' ? (
                        <FileUp className="h-4 w-4" />
                      ) : (
                        <Activity className="h-4 w-4" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-medium">{event.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatRelativeTime(new Date(event.timestamp))}
                      </p>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/40 opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5" />
                  </Link>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/40">
                    <Activity className="h-7 w-7 text-muted-foreground/40" />
                  </div>
                  <p className="mt-4 text-sm font-medium text-muted-foreground">No recent activity</p>
                  <p className="mt-1 text-xs text-muted-foreground/60">Activity will appear here as you use the console</p>
                </div>
              )}
            </div>
          </StaggerItem>

          {/* Sidebar Stats */}
          <StaggerItem className="lg:col-span-2 space-y-5">
            {/* Quick actions mini-card */}
            <div className="surface p-6">
              <h3 className="label-caps">Quick Actions</h3>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {[
                  { label: 'Ask AI', href: '/ask', icon: MessageCircleQuestion, accent: 'primary' },
                  { label: 'Upload', href: '/ingest', icon: FileUp, accent: 'accent' },
                  { label: 'Browse', href: '/retrieval', icon: Database, accent: 'chart-3' },
                  { label: 'Team', href: '/team', icon: Users, accent: 'chart-5' },
                ].map((action) => (
                  <Link
                    key={action.href}
                    href={action.href}
                    className="group flex flex-col items-center gap-2 rounded-xl bg-muted/20 py-4 text-center text-xs font-medium text-muted-foreground transition-all hover:bg-muted/40 hover:text-foreground"
                  >
                    <action.icon className="h-5 w-5 transition-transform group-hover:scale-110" />
                    {action.label}
                  </Link>
                ))}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="surface p-6">
              <h3 className="label-caps">Today&apos;s Snapshot</h3>
              <dl className="mt-5 space-y-4">
                {[
                  { label: 'Queries', color: 'bg-primary', value: activity?.filter((e) => e.type === 'query').length ?? 0 },
                  { label: 'Documents', color: 'bg-accent', value: activity?.filter((e) => e.type === 'ingestion').length ?? 0 },
                  { label: 'Errors', color: 'bg-destructive', value: activity?.filter((e) => e.type === 'error').length ?? 0, isError: true },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between">
                    <dt className="flex items-center gap-2.5 text-sm text-muted-foreground">
                      <span className={`h-2 w-2 rounded-full ${item.color}`} />
                      {item.label}
                    </dt>
                    <dd className={`text-lg font-bold stat-number ${item.isError && item.value > 0 ? 'text-destructive' : ''}`}>
                      {item.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* System Status */}
            <div className="surface p-6">
              <h3 className="label-caps">System Health</h3>
              <div className="mt-5 space-y-2.5">
                  {[
                    { name: 'API', status: 'Connected', ok: true },
                    { name: 'Vector Store', status: 'Ready', ok: true },
                    { name: 'Mode', status: mockMode ? 'Mock Blend' : 'Live', ok: !mockMode },
                ].map((service) => (
                  <div key={service.name} className="flex items-center justify-between rounded-lg bg-muted/30 px-3.5 py-2.5">
                    <div className="flex items-center gap-2.5">
                      <span className={`status-dot ${service.ok ? 'status-dot--ok' : 'status-dot--warn'}`} style={{ width: 7, height: 7 }} />
                      <span className="text-sm">{service.name}</span>
                    </div>
                    <span className={`text-xs font-medium ${service.ok ? 'text-success' : 'text-warning'}`}>
                      {service.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </StaggerItem>
        </StaggerContainer>
      </div>
    </div>
  )
}
