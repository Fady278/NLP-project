'use client'

import { useState } from 'react'
import { Search, Filter, X, Copy, Check, FileText, Code, Sparkles, SlidersHorizontal, Database, BadgeInfo, FolderSearch, ScanSearch, Quote } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { useChunks } from '@/lib/hooks/use-rag'
import type { RetrievedChunk, RetrievalFilter } from '@/lib/models/types'
import { FadeIn, StaggerContainer, StaggerItem } from '@/components/ui/fade-in'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { cn } from '@/lib/utils'

const FILE_TYPES = ['pdf', 'md', 'txt', 'docx', 'html']

export default function RetrievalPage() {
  const [filters, setFilters] = useState<RetrievalFilter>({})
  const [sourceSearch, setSourceSearch] = useState('')
  const [selectedChunk, setSelectedChunk] = useState<RetrievedChunk | null>(null)
  const [showJson, setShowJson] = useState(false)
  const [copied, setCopied] = useState(false)

  const { data, isLoading } = useChunks(filters)

  const handleSourceSearch = (value: string) => {
    setSourceSearch(value)
    setFilters((prev) => ({
      ...prev,
      sourceFile: value || undefined,
    }))
  }

  const handleTypeFilter = (value: string[]) => {
    setFilters((prev) => {
      if (value.length === 0) {
        const { fileType: _, ...rest } = prev
        return rest
      }

      return {
        ...prev,
        fileType: value,
      }
    })
  }

  const handleScoreFilter = (value: number[]) => {
    setFilters((prev) => ({
      ...prev,
      minScore: value[0] / 100,
      maxScore: value[1] / 100,
    }))
  }

  const clearFilters = () => {
    setFilters({})
    setSourceSearch('')
  }

  const hasActiveFilters =
    filters.sourceFile || filters.fileType?.length || filters.minScore !== undefined

  const handleCopyJson = async () => {
    if (!selectedChunk) return
    await navigator.clipboard.writeText(JSON.stringify(selectedChunk, null, 2))
    setCopied(true)
    toast.success('Copied to clipboard')
    setTimeout(() => setCopied(false), 2000)
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'bg-success/10 text-success'
    if (score >= 0.6) return 'bg-warning/10 text-warning'
    return 'bg-muted text-muted-foreground'
  }

  const averageScore =
    data?.chunks.length
      ? Math.round(
          (data.chunks.reduce((sum, chunk) => sum + chunk.score, 0) / data.chunks.length) * 100
        )
      : 0

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-6xl space-y-6 pb-8">
        <FadeIn direction="up">
          <section className="relative overflow-hidden rounded-2xl surface p-8 md:p-10">
            <div className="orb orb-amber" style={{ width: 180, height: 180, top: -40, right: -20 }} />
            <div className="orb orb-teal" style={{ width: 130, height: 130, bottom: -30, left: '16%' }} />

            <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                  Retrieval Observatory
                </div>
                <h1 className="mt-4 text-3xl font-bold tracking-tight lg:text-4xl">
                  Inspect <span className="text-gradient">retrieval quality</span> with clarity
                </h1>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground md:text-base">
                  Explore indexed chunks, validate relevance signals, and audit what the system can
                  actually surface before those results reach the answer layer.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="surface-raised min-w-[120px] p-4">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                    <Database className="h-4 w-4 text-primary" />
                  </div>
                  <p className="mt-3 text-2xl font-bold stat-number">{data?.total ?? 0}</p>
                  <p className="text-xs text-muted-foreground">Visible Chunks</p>
                </div>
                <div className="surface-raised min-w-[120px] p-4">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
                    <Filter className="h-4 w-4 text-accent" />
                  </div>
                  <p className="mt-3 text-2xl font-bold stat-number">{hasActiveFilters ? 'On' : 'Off'}</p>
                  <p className="text-xs text-muted-foreground">Filter State</p>
                </div>
                <div className="surface-raised min-w-[120px] p-4 col-span-2 sm:col-span-1">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-chart-3/10">
                    <BadgeInfo className="h-4 w-4 text-chart-3" />
                  </div>
                  <p className="mt-3 text-2xl font-bold stat-number">{averageScore}%</p>
                  <p className="text-xs text-muted-foreground">Avg. Score</p>
                </div>
              </div>
            </div>
          </section>
        </FadeIn>

        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="label-caps">Inspection Controls</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Filter by source, type, and score to isolate the chunks you actually care about.
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="surface p-5 md:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted/40">
                <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <h2 className="text-sm font-semibold">Query Filters</h2>
                <p className="text-xs text-muted-foreground">Refine the visible retrieval surface</p>
              </div>
            </div>

            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="gap-1 rounded-lg">
                <X className="h-3.5 w-3.5" />
                Clear filters
              </Button>
            )}
          </div>

          <div className="flex flex-wrap items-end gap-4">
            {/* Source Search */}
            <div className="min-w-[200px] flex-1">
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Source File
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by filename..."
                  value={sourceSearch}
                  onChange={(e) => handleSourceSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            {/* File Type */}
            <div className="min-w-[240px] flex-1">
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                File Types
              </label>
              <ToggleGroup
                type="multiple"
                value={filters.fileType ?? []}
                onValueChange={handleTypeFilter}
                variant="outline"
                className="flex flex-wrap gap-2"
              >
                {FILE_TYPES.map((type) => (
                  <ToggleGroupItem
                    key={type}
                    value={type}
                    aria-label={`Filter by .${type} files`}
                    className="rounded-full px-3 data-[state=on]:border-primary/40 data-[state=on]:bg-primary/12 data-[state=on]:text-primary"
                  >
                    .{type}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              <p className="mt-2 text-xs text-muted-foreground">
                Tap one or more file types. Leave all unselected to show everything.
              </p>
            </div>

            {/* Score Range */}
            <div className="w-[220px]">
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Score Range: {((filters.minScore ?? 0) * 100).toFixed(0)}% –{' '}
                {((filters.maxScore ?? 1) * 100).toFixed(0)}%
              </label>
              <Slider
                value={[
                  (filters.minScore ?? 0) * 100,
                  (filters.maxScore ?? 1) * 100,
                ]}
                onValueChange={handleScoreFilter}
                min={0}
                max={100}
                step={5}
              />
            </div>

          </div>

          {hasActiveFilters && (
            <div className="mt-4 flex flex-wrap gap-2">
              {filters.sourceFile && <span className="chip">Source: {filters.sourceFile}</span>}
              {filters.fileType?.map((type) => (
                <span key={type} className="chip">Type: .{type}</span>
              ))}
              {(filters.minScore !== undefined || filters.maxScore !== undefined) && (
                <span className="chip">
                  Score: {Math.round((filters.minScore ?? 0) * 100)}% - {Math.round((filters.maxScore ?? 1) * 100)}%
                </span>
              )}
            </div>
          )}
        </div>

        {/* Results */}
        <div className="space-y-4">
          <div className="surface-raised flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                <Search className="h-4.5 w-4.5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {isLoading
                    ? 'Loading retrieval results...'
                    : `${data?.total ?? 0} chunk${data?.total !== 1 ? 's' : ''} found`}
                </p>
                <p className="text-xs text-muted-foreground">
                  {hasActiveFilters
                    ? 'Showing the current filtered retrieval surface'
                    : 'Showing the current indexed retrieval surface'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto">
              {hasActiveFilters && (
                <div className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary">
                  <Filter className="h-3 w-3" />
                  Filtered
                </div>
              )}

              {!isLoading && (
                <div className="rounded-full bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
                  Avg score {averageScore}%
                </div>
              )}
            </div>
          </div>

          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="surface p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <Skeleton className="h-5 w-1/2" />
                    <Skeleton className="h-5 w-12" />
                  </div>
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-4 w-1/3" />
                </div>
              ))}
            </div>
          ) : !data?.chunks.length ? (
            <FadeIn direction="up">
              <div className="surface flex flex-col items-center justify-center py-16 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/30">
                  <Search className="h-7 w-7 text-muted-foreground/40" />
                </div>
                <h3 className="mt-4 font-semibold">No chunks found</h3>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  {hasActiveFilters
                    ? 'Try adjusting your filters to see more results.'
                    : 'Your knowledge base is empty. Upload some documents to get started.'}
                </p>
              </div>
            </FadeIn>
          ) : (
            <StaggerContainer className="grid gap-3 sm:grid-cols-2">
              {data.chunks.map((chunk) => (
                <StaggerItem key={chunk.id}>
                  <button
                    type="button"
                    className="surface-raised animated-border w-full cursor-pointer overflow-hidden p-0 text-left transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_14px_36px_rgba(11,58,114,0.10)]"
                    onClick={() => setSelectedChunk(chunk)}
                  >
                    <div className="border-b border-border/35 bg-muted/15 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 text-sm">
                            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-background/80 ring-1 ring-border/60">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                            </div>
                            <div className="min-w-0">
                              <span className="block truncate font-semibold max-w-[220px] text-foreground">
                                {chunk.source}
                              </span>
                              <span className="text-[11px] text-muted-foreground">
                                {chunk.pageNumber ? `Page ${chunk.pageNumber}` : 'Indexed chunk'}
                                {chunk.section ? ' • Evidence snippet' : ''}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <Badge
                            variant="secondary"
                            className={cn('shrink-0 rounded-full border-0 px-2.5 py-1 text-[11px]', getScoreColor(chunk.score))}
                          >
                            {(chunk.score * 100).toFixed(0)}%
                          </Badge>
                          <span className="label-caps text-[10px]">Match</span>
                        </div>
                      </div>
                    </div>

                    <div className="px-4 py-4">
                      <p className="line-clamp-4 text-sm leading-7 text-muted-foreground">
                        {chunk.text}
                      </p>

                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        {chunk.pageNumber && (
                          <span className="chip bg-primary/8 text-primary hover:bg-primary/12">
                            Page {chunk.pageNumber}
                          </span>
                        )}
                        {chunk.section && (
                          <span className="chip max-w-[220px] truncate bg-accent/10 text-accent hover:bg-accent/15">
                            {chunk.section}
                          </span>
                        )}
                        {!chunk.pageNumber && !chunk.section && (
                          <span className="chip">Metadata-light chunk</span>
                        )}
                      </div>

                      <div className="mt-4 flex items-center justify-between border-t border-border/30 pt-3">
                        <span className="text-xs text-muted-foreground">
                          Click to inspect full content
                        </span>
                        <span className="text-xs font-medium text-primary">
                          Open details
                        </span>
                      </div>
                    </div>
                  </button>
                </StaggerItem>
              ))}
            </StaggerContainer>
          )}
        </div>

        {/* Detail Sheet */}
        <Sheet open={!!selectedChunk} onOpenChange={() => setSelectedChunk(null)}>
          <SheetContent className="w-full sm:max-w-xl overflow-hidden p-0">
            <SheetHeader>
              <div className="border-b border-border/40 px-6 pt-6 pb-4">
                <SheetTitle className="text-xl">Chunk Details</SheetTitle>
                <SheetDescription>
                {selectedChunk?.source}
                {selectedChunk?.pageNumber && ` • Page ${selectedChunk.pageNumber}`}
                </SheetDescription>
              </div>
            </SheetHeader>

            {selectedChunk && (
              <ScrollArea className="h-[calc(100vh-96px)]">
                <div className="space-y-6 px-6 py-6">
                  <div className="relative overflow-hidden rounded-2xl surface p-5">
                  <div className="orb orb-amber" style={{ width: 120, height: 120, top: -18, right: -12 }} />
                  <div className="relative z-10">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10">
                          <FolderSearch className="h-5 w-5 text-primary" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-foreground">{selectedChunk.source}</p>
                          <p className="mt-1 text-xs text-muted-foreground">Retrieval evidence candidate</p>
                        </div>
                      </div>
                      <Badge
                        variant="secondary"
                        className={cn('rounded-full border-0 px-3 py-1.5 text-xs font-semibold', getScoreColor(selectedChunk.score))}
                      >
                        {(selectedChunk.score * 100).toFixed(1)}%
                      </Badge>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {selectedChunk.pageNumber && (
                        <span className="chip bg-primary/8 text-primary hover:bg-primary/12">
                          Page {selectedChunk.pageNumber}
                        </span>
                      )}
                      {selectedChunk.section && (
                        <span className="chip max-w-[240px] truncate bg-accent/10 text-accent hover:bg-accent/15">
                          {selectedChunk.section}
                        </span>
                      )}
                      {!selectedChunk.pageNumber && !selectedChunk.section && (
                        <span className="chip">Metadata-light chunk</span>
                      )}
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-xl bg-muted/25 p-3">
                        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                          <ScanSearch className="h-3.5 w-3.5" />
                          Relevance Score
                        </div>
                        <div className="mt-3 flex items-center gap-3">
                          <div className="h-2.5 flex-1 rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all"
                              style={{ width: `${selectedChunk.score * 100}%` }}
                            />
                          </div>
                          <span className="text-sm font-bold stat-number">
                            {(selectedChunk.score * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      <div className="rounded-xl bg-muted/25 p-3">
                        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                          <BadgeInfo className="h-3.5 w-3.5" />
                          Metadata Surface
                        </div>
                        <p className="mt-3 text-sm text-foreground">
                          {selectedChunk.metadata && Object.keys(selectedChunk.metadata).length > 0
                            ? `${Object.keys(selectedChunk.metadata).length} metadata field${Object.keys(selectedChunk.metadata).length !== 1 ? 's' : ''}`
                            : 'Minimal metadata available'}
                        </p>
                      </div>
                    </div>
                  </div>
                  </div>

                  {/* Text Content */}
                  <div className="surface-raised p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Chunk Content</label>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Full retrieval text with raw inspection support
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 rounded-lg"
                        onClick={() => setShowJson(!showJson)}
                      >
                        <Code className="mr-1 h-3 w-3" />
                        {showJson ? 'Text' : 'JSON'}
                      </Button>
                    </div>
                    <ScrollArea className="mt-4 h-[320px] rounded-xl border border-border/40 bg-muted/20 p-4">
                      {showJson ? (
                        <pre className="font-mono text-xs whitespace-pre-wrap">
                          {JSON.stringify(selectedChunk, null, 2)}
                        </pre>
                      ) : (
                        <div className="relative">
                          <Quote className="absolute left-0 top-0 h-4 w-4 text-primary/40" />
                          <p className="whitespace-pre-wrap pl-6 text-sm leading-7 text-foreground/90">
                            {selectedChunk.text}
                          </p>
                        </div>
                      )}
                    </ScrollArea>
                  </div>

                  {/* Metadata */}
                  {selectedChunk.metadata &&
                    Object.keys(selectedChunk.metadata).length > 0 && (
                      <div className="surface-raised p-4">
                        <div>
                          <label className="text-xs font-medium text-muted-foreground">Metadata</label>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Structured fields attached to this chunk
                          </p>
                        </div>
                        <div className="mt-3 space-y-2">
                          {Object.entries(selectedChunk.metadata).map(([key, value]) => (
                            <div
                              key={key}
                              className="flex items-start justify-between gap-4 rounded-lg bg-muted/30 px-3 py-2 text-sm"
                            >
                              <span className="text-muted-foreground">{key}</span>
                              <span className="max-w-[60%] text-right font-medium break-words">{String(value)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  {/* Actions */}
                  <div className="sticky bottom-0 -mx-6 border-t border-border/40 bg-background/92 px-6 py-4 backdrop-blur-xl">
                    <div className="flex gap-2">
                      <Button className="h-11 flex-1 btn-glow rounded-xl" onClick={handleCopyJson}>
                        {copied ? (
                          <>
                            <Check className="mr-2 h-4 w-4" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="mr-2 h-4 w-4" />
                            Copy as JSON
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            )}
          </SheetContent>
        </Sheet>
        </div>
      </div>
    </div>
  )
}
