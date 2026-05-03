'use client'

import { useEffect, useMemo, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  BrainCircuit,
  FileText,
  MessageCircleQuestion,
  Plus,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { motion } from 'framer-motion'

import { QueryComposer } from '@/components/rag/query-composer'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { consumePendingChatQuestion } from '@/lib/config/api'
import { useIngestionJobs, useRagQuery, useRelativeTime } from '@/lib/hooks/use-rag'

export default function AskPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const formatRelativeTime = useRelativeTime()
  const processedQueryRef = useRef<string>('')
  const legacyQuestion = searchParams.get('q')?.trim() || ''
  const { data: ingestionJobs } = useIngestionJobs()

  const {
    hydrated,
    sessions,
    activeSession,
    activeSessionId,
    setActiveSessionId,
    createSession,
    openQuestion,
    deleteSession,
    answers,
    selectedAnswer,
    setSelectedAnswer,
    submitQuestion,
    isLoading,
  } = useRagQuery()

  const latestUploadedJob = useMemo(() => {
    return [...(ingestionJobs ?? [])]
      .filter((job) => job.status === 'indexed' && job.fileType !== 'directory')
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())[0]
  }, [ingestionJobs])

  const suggestionQuestions = useMemo(() => {
    const latestFile = latestUploadedJob?.fileName
    if (!latestFile) {
      return [
        'What is RAG?',
        'Summarize the most recent uploaded document.',
        'What are the key topics in the latest document?',
      ]
    }

    return [
      `Summarize the main ideas in ${latestFile}.`,
      `What are the most important points mentioned in ${latestFile}?`,
      `Give me a concise overview of ${latestFile}.`,
    ]
  }, [latestUploadedJob])

  useEffect(() => {
    if (!hydrated) return

    const pendingQuestion = consumePendingChatQuestion() || legacyQuestion
    if (!pendingQuestion) return
    if (processedQueryRef.current === pendingQuestion) return

    processedQueryRef.current = pendingQuestion
    if (legacyQuestion && typeof window !== 'undefined') {
      const nextUrl = `${window.location.pathname}${window.location.hash || ''}`
      window.history.replaceState({}, '', nextUrl)
      router.replace('/ask', { scroll: false })
    }

    if (openQuestion(pendingQuestion)) return
    void submitQuestion(pendingQuestion)
  }, [hydrated, legacyQuestion, openQuestion, router, submitQuestion])

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="shrink-0 border-b border-border/40 bg-card/20 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-primary/90 to-accent/60">
              <BrainCircuit className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">Ask AI</h1>
              <p className="text-xs text-muted-foreground">Persistent chat sessions over your knowledge base</p>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="gap-2 rounded-xl"
            onClick={() => createSession()}
          >
            <Plus className="h-4 w-4" />
            New chat
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="hidden min-h-0 w-[320px] shrink-0 flex-col border-r border-border/40 bg-card/10 xl:flex">
          <div className="shrink-0 border-b border-border/40 px-4 py-3">
            <h2 className="text-sm font-semibold">Sessions</h2>
            <p className="mt-1 text-xs text-muted-foreground">Your recent conversations are cached locally.</p>
          </div>

          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-2 p-3">
              {!hydrated ? (
                Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="rounded-2xl border border-border/30 bg-card/20 p-4">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="mt-3 h-3 w-1/2" />
                  </div>
                ))
              ) : sessions.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border/50 bg-muted/10 p-4 text-sm text-muted-foreground">
                  Start a new chat to build your first session.
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className={`rounded-2xl border p-4 transition-all ${
                      activeSessionId === session.id
                        ? 'border-primary/40 bg-primary/5 ring-1 ring-primary/15'
                        : 'border-border/30 bg-card/20 hover:border-primary/20 hover:bg-muted/20'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveSessionId(session.id)
                          setSelectedAnswer(null)
                        }}
                        className="min-w-0 flex-1 text-left"
                      >
                        <p className="line-clamp-2 text-sm font-medium leading-5">{session.title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {session.answers.length} turn{session.answers.length !== 1 ? 's' : ''} · {formatRelativeTime(session.updatedAt)}
                        </p>
                      </button>
                      <button
                        type="button"
                        className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        onClick={(event) => {
                          deleteSession(session.id)
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <ScrollArea className="flex-1 min-h-0">
            <div className="mx-auto max-w-3xl px-6 py-8">
              {isLoading && answers.length === 0 ? (
                <div className="space-y-6">
                  <div className="mx-auto max-w-2xl rounded-3xl border border-border/30 bg-card/20 p-6">
                    <div className="mb-6 flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                        <BrainCircuit className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <Skeleton className="h-4 w-40" />
                        <Skeleton className="mt-2 h-3 w-28" />
                      </div>
                    </div>
                    <div className="ml-auto max-w-[70%]">
                      <div className="rounded-2xl rounded-br-md bg-primary/10 p-4">
                        <Skeleton className="h-4 w-48" />
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                        <BrainCircuit className="h-4 w-4 text-primary" />
                      </div>
                      <div className="flex-1 space-y-3 rounded-2xl rounded-tl-md border border-border/40 bg-card/30 p-4">
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-5/6" />
                        <Skeleton className="h-4 w-4/6" />
                      </div>
                    </div>
                  </div>
                </div>
              ) : answers.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5 }}
                  className="flex h-full flex-col items-center justify-center py-20"
                >
                  <div className="relative">
                    <div className="orb orb-amber" style={{ width: 100, height: 100, top: -20, left: -20 }} />
                    <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-accent/10 ring-1 ring-primary/20">
                      <MessageCircleQuestion className="h-10 w-10 text-primary" />
                    </div>
                  </div>
                  <h2 className="mt-6 text-xl font-bold">Ask anything</h2>
                  <p className="mt-2 max-w-sm text-center text-sm leading-relaxed text-muted-foreground">
                    Sessions are cached locally, and the last few turns are sent intelligently as context instead of dumping the whole chat every time.
                  </p>
                  {latestUploadedJob && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Latest uploaded file: <span className="font-medium text-foreground">{latestUploadedJob.fileName}</span>
                    </p>
                  )}
                  <div className="mt-8 flex flex-wrap justify-center gap-2">
                    {suggestionQuestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => void submitQuestion(suggestion)}
                        className="chip transition-all hover:bg-primary/10 hover:text-primary"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                <div className="space-y-6">
                  {answers.map((answer) => (
                    <motion.div
                      key={answer.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.35 }}
                    >
                      <div className="space-y-4">
                        <div className="ml-auto max-w-[80%]">
                          <div className="rounded-2xl rounded-br-md bg-primary px-4 py-3 text-primary-foreground">
                            <p className="text-sm">{answer.question}</p>
                          </div>
                        </div>

                        <div className="flex gap-3">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary/15 to-accent/10 ring-1 ring-primary/20">
                            <BrainCircuit className="h-4 w-4 text-primary" />
                          </div>
                          <div
                            className={`group flex-1 cursor-pointer rounded-2xl rounded-tl-md border p-4 transition-all ${
                              selectedAnswer?.id === answer.id
                                ? 'border-primary/40 bg-primary/5 ring-1 ring-primary/15'
                                : 'border-border/40 bg-card/30 hover:border-primary/25'
                            }`}
                            onClick={() => setSelectedAnswer(selectedAnswer?.id === answer.id ? null : answer)}
                          >
                            {answer.status === 'pending' ? (
                              <div className="flex items-center gap-1.5 py-1">
                                <span className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                                <span className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                                <span className="h-2 w-2 animate-bounce rounded-full bg-primary" />
                              </div>
                            ) : answer.status === 'error' ? (
                              <div className="space-y-3">
                                <p className="text-sm text-destructive font-medium">Failed to get an answer.</p>
                                <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); submitQuestion(answer.question, undefined, answer.id) }}>Retry</Button>
                              </div>
                            ) : (
                              <>
                                <p className="whitespace-pre-wrap text-sm leading-relaxed">{answer.answer}</p>

                                {answer.chunks.length > 0 && (
                                  <div className="mt-4 flex flex-wrap gap-2">
                                    {answer.chunks.slice(0, 3).map((chunk) => (
                                      <Badge
                                        key={chunk.id}
                                        variant="secondary"
                                        className="gap-1.5 bg-muted/40 text-xs font-normal"
                                      >
                                        <FileText className="h-3 w-3" />
                                        {chunk.source?.split(/[\\/]/).pop()?.slice(0, 24) || 'Unknown source'}
                                      </Badge>
                                    ))}
                                    {answer.chunks.length > 3 && (
                                      <Badge variant="secondary" className="bg-muted/40 text-xs font-normal">
                                        +{answer.chunks.length - 3} more
                                      </Badge>
                                    )}
                                  </div>
                                )}

                                <p className="mt-3 text-xs text-muted-foreground">
                                  Click to {selectedAnswer?.id === answer.id ? 'hide' : 'view'} sources
                                </p>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}


                </div>
              )}
            </div>
          </ScrollArea>

          <div className="shrink-0 border-t border-border/40 bg-card/20 px-6 py-4 backdrop-blur-sm">
            <div className="mx-auto max-w-3xl space-y-2">
              <QueryComposer onSubmit={submitQuestion} isLoading={isLoading} />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5" />
                  Session-aware UI with cached local chat history
                </span>
                {activeSession && (
                  <span>{activeSession.answers.length} message{activeSession.answers.length !== 1 ? 's' : ''}</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {selectedAnswer && (
          <div className="hidden min-h-0 w-[420px] shrink-0 border-l border-border/40 bg-card/20 lg:block">
            <div className="flex h-full min-h-0 flex-col">
              <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
                <h3 className="text-sm font-semibold">Sources</h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={() => setSelectedAnswer(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <ScrollArea className="flex-1 min-h-0">
                <div className="space-y-3 p-4">
                  {selectedAnswer.chunks.map((chunk) => (
                    <div key={chunk.id} className="surface-raised group p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="h-3.5 w-3.5 text-primary" />
                          </div>
                          <div>
                            <p className="text-sm font-medium leading-none">
                              {chunk.source?.split(/[\\/]/).pop() || 'Unknown'}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {chunk.pageNumber ? `Page ${chunk.pageNumber}` : `Score ${Math.round(chunk.score * 100)}%`}
                            </p>
                          </div>
                        </div>
                        <Badge
                          className={`text-xs ${
                            chunk.score >= 0.8
                              ? 'bg-success/10 text-success'
                              : chunk.score >= 0.6
                                ? 'bg-warning/10 text-warning'
                                : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          {Math.round(chunk.score * 100)}%
                        </Badge>
                      </div>
                      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{chunk.text}</p>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
