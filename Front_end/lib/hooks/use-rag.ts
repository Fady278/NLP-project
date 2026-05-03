'use client'

// ============================================
// TanStack Query Hooks for RAG Console
// ============================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useCallback, useEffect, useMemo } from 'react'
import { toast } from 'sonner'
import type {
  QueryAnswer,
  QueryRequest,
  IngestionJob,
  IngestRequest,
  RetrievalFilter,
  ChatSession,
  ActivityEvent,
} from '@/lib/models/types'
import * as api from '@/lib/api/client'
import {
  CHAT_SESSIONS_STORAGE_KEY,
  POLLING_INTERVALS,
} from '@/lib/config/api'
import { useMockMode } from '@/lib/hooks/use-api-mode'
import { normalizeChunk } from '@/lib/normalizers'

function formatQueryError(error: unknown): string {
  const message = error instanceof Error ? error.message : 'Query failed'

  if (message.includes('request_quota_exceeded') || message.includes('Requests per minute limit exceeded')) {
    return 'Cerebras rate limit exceeded. Please wait a minute and try again.'
  }

  if (message.includes('1010')) {
    return 'Cerebras blocked this request. Please try again in a minute or switch networks.'
  }

  if (message.includes('Failed to fetch')) {
    return 'Backend is offline or unreachable. Please make sure the API server is running.'
  }

  return message
}

// -----------------------------------------
// Query Keys
// -----------------------------------------

export const queryKeys = {
  stats: ['stats'] as const,
  activity: ['activity'] as const,
  documents: ['documents'] as const,
  document: (id: string) => ['documents', id] as const,
  ingestionJobs: ['ingestion-jobs'] as const,
  ingestionJob: (id: string) => ['ingestion-jobs', id] as const,
  chunks: (filters?: RetrievalFilter) => ['chunks', filters] as const,
}

// -----------------------------------------
// Dashboard Hooks
// -----------------------------------------

export function useStats() {
  const { mockMode } = useMockMode()

  return useQuery({
    queryKey: [...queryKeys.stats, mockMode] as const,
    queryFn: api.getStats,
    refetchInterval: POLLING_INTERVALS.stats,
  })
}

export function useActivity() {
  const { mockMode } = useMockMode()

  return useQuery({
    queryKey: [...queryKeys.activity, mockMode] as const,
    queryFn: api.getActivity,
    refetchInterval: POLLING_INTERVALS.activity,
  })
}

// -----------------------------------------
// Query Hook with Local History
// -----------------------------------------

export function useRagQuery() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [selectedAnswer, setSelectedAnswer] = useState<QueryAnswer | null>(null)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return

    const restoreFromActivity = async () => {
      try {
        const activity = await api.getActivity()
        const restoredSessions = buildSessionsFromActivity(activity)
        if (restoredSessions.length === 0) {
          setHydrated(true)
          return
        }

        setSessions(restoredSessions)
        setActiveSessionId(restoredSessions[0].id)
        window.localStorage.setItem(CHAT_SESSIONS_STORAGE_KEY, JSON.stringify(restoredSessions))
      } catch {
        // Ignore restore failures and continue with an empty state.
      }
      setHydrated(true)
    }

    try {
      const raw = window.localStorage.getItem(CHAT_SESSIONS_STORAGE_KEY)
      if (!raw) {
        void restoreFromActivity()
        return
      }
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) {
        void restoreFromActivity()
        return
      }

      const restoredSessions: ChatSession[] = parsed.map((item, index) => {
        const record = item as Partial<ChatSession> & { answers?: QueryAnswer[] }
        const answers = Array.isArray(record.answers)
          ? record.answers.map((answer) => ({
              ...answer,
              timestamp: new Date(answer.timestamp),
            }))
          : []

        return {
          id: record.id || `session-${index}`,
          title: record.title || 'Untitled chat',
          createdAt: record.createdAt ? new Date(record.createdAt) : new Date(),
          updatedAt: record.updatedAt ? new Date(record.updatedAt) : new Date(),
          answers,
        }
      })

      setSessions(restoredSessions)
      if (restoredSessions.length > 0) {
        setActiveSessionId(restoredSessions[0].id)
      } else {
        void restoreFromActivity()
        return
      }
    } catch {
      void restoreFromActivity()
      return
    }
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined' || !hydrated) return
    window.localStorage.setItem(CHAT_SESSIONS_STORAGE_KEY, JSON.stringify(sessions))
  }, [hydrated, sessions])

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [sessions, activeSessionId]
  )

  const answers = activeSession?.answers ?? []

  const buildConversationContext = useCallback((sessionAnswers: QueryAnswer[]) => {
    const recentTurns = sessionAnswers.slice(-3)
    if (recentTurns.length === 0) return undefined

    const parts: string[] = []
    let totalChars = 0

    for (const answer of recentTurns) {
      const nextPart =
        `User: ${answer.question}\nAssistant: ${answer.answer}`.trim()
      if (!nextPart) continue
      if (totalChars + nextPart.length > 1800) break
      parts.push(nextPart)
      totalChars += nextPart.length
    }

    return parts.length > 0 ? parts.join('\n\n') : undefined
  }, [])

  const createSession = useCallback((seedQuestion?: string) => {
    const now = new Date()
    const nextSession: ChatSession = {
      id: `session-${now.getTime()}`,
      title: seedQuestion?.trim() || 'New chat',
      createdAt: now,
      updatedAt: now,
      answers: [],
    }

    setSessions((prev) => [nextSession, ...prev])
    setActiveSessionId(nextSession.id)
    setSelectedAnswer(null)
    return nextSession.id
  }, [])

  const openQuestion = useCallback((question: string) => {
    const normalized = question.trim().toLowerCase()
    if (!normalized) return false

    for (const session of sessions) {
      const matchedAnswer = session.answers.find(
        (answer) => answer.question.trim().toLowerCase() === normalized
      )
      if (!matchedAnswer) continue

      setActiveSessionId(session.id)
      setSelectedAnswer(matchedAnswer)
      return true
    }

    return false
  }, [sessions])

  const mutation = useMutation({
    mutationFn: ({ request, tempId }: { request: QueryRequest; sessionId: string; tempId: string }) => api.submitQuery(request),
    onSuccess: (data, variables) => {
      const now = new Date()
      setSessions((prev) => {
        const targetSessionId = variables.sessionId
        const updated = prev.map((session) => {
          if (session.id !== targetSessionId) return session

          const nextAnswers = session.answers.map(ans =>
            ans.id === variables.tempId ? { ...data, status: 'success' as const } : ans
          )
          
          return {
            ...session,
            title: session.answers.length === 1 && session.answers[0].id === variables.tempId ? variables.request.question : session.title,
            updatedAt: now,
            answers: nextAnswers,
          }
        })

        if (updated.some((session) => session.id === targetSessionId)) {
          return updated.sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
        }

        return [
          {
            id: targetSessionId,
            title: variables.request.question,
            createdAt: now,
            updatedAt: now,
            answers: [{ ...data, status: 'success' as const }],
          },
          ...updated,
        ]
      })
      setActiveSessionId(variables.sessionId)
      setSelectedAnswer({ ...data, status: 'success' })
    },
    onError: (error, variables) => {
      setSessions((prev) => {
        return prev.map(session => {
          if (session.id !== variables.sessionId) return session
          const nextAnswers = session.answers.map(ans =>
            ans.id === variables.tempId ? { ...ans, status: 'error' as const } : ans
          )
          return { ...session, answers: nextAnswers }
        })
      })
      toast.error(formatQueryError(error))
    },
  })

  const submitQuestion = useCallback(
    async (question: string, topK?: number, retryId?: string) => {
      const sessionId = activeSessionId ?? createSession(question)
      const session = sessions.find((item) => item.id === sessionId)
      const conversationContext = buildConversationContext(session?.answers ?? [])
      
      const tempId = retryId || `temp-${Date.now()}`
      const tempAnswer: QueryAnswer = {
        id: tempId,
        question,
        answer: '',
        chunks: [],
        timestamp: new Date(),
        status: 'pending'
      }

      setSessions((prev) => {
        return prev.map(s => {
          if (s.id !== sessionId) return s
          
          let nextAnswers = [...s.answers]
          if (retryId) {
            nextAnswers = nextAnswers.map(ans => ans.id === retryId ? tempAnswer : ans)
          } else {
            nextAnswers.push(tempAnswer)
          }
          
          return { ...s, answers: nextAnswers }
        })
      })

      try {
        return await mutation.mutateAsync({
          sessionId,
          tempId,
          request: { question, topK, conversationContext },
        })
      } catch {
        return null
      }
    },
    [activeSessionId, buildConversationContext, createSession, mutation, sessions]
  )

  const clearHistory = useCallback(() => {
    if (!activeSessionId) return
    setSessions((prev) =>
      prev.map((session) =>
        session.id === activeSessionId
          ? { ...session, answers: [], updatedAt: new Date() }
          : session
      )
    )
    setSelectedAnswer(null)
  }, [activeSessionId])

  const deleteSession = useCallback((sessionId: string) => {
    setSessions((prev) => {
      const remaining = prev.filter((session) => session.id !== sessionId)
      if (activeSessionId === sessionId) {
        setActiveSessionId(remaining[0]?.id ?? null)
        setSelectedAnswer(null)
      }
      return remaining
    })
  }, [activeSessionId])

  return {
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
    clearHistory,
    isLoading: mutation.isPending,
    error: mutation.error,
  }
}

function buildSessionsFromActivity(activity: ActivityEvent[]): ChatSession[] {
  const queryEvents = activity.filter((event) => {
    if (event.type !== 'query') return false
    const metadata = event.metadata ?? {}
    return typeof metadata.question === 'string' && typeof metadata.answer === 'string'
  })

  return queryEvents.map((event, index) => {
    const metadata = event.metadata ?? {}
    const timestamp = event.timestamp instanceof Date ? event.timestamp : new Date(event.timestamp)
    const restoredAnswer: QueryAnswer = {
      id: `activity-answer-${event.id}`,
      question: String(metadata.question ?? event.description),
      answer: String(metadata.answer ?? ''),
      chunks: Array.isArray(metadata.retrieved_context)
        ? metadata.retrieved_context.map((chunk, chunkIndex) => normalizeChunk(chunk, chunkIndex))
        : [],
      timestamp,
      modelUsed: typeof metadata.model_used === 'string' ? metadata.model_used : undefined,
      metadata:
        metadata.response_metadata && typeof metadata.response_metadata === 'object'
          ? (metadata.response_metadata as Record<string, unknown>)
          : undefined,
      status: 'success',
    }

    return {
      id: `activity-session-${event.id}`,
      title: restoredAnswer.question,
      createdAt: timestamp,
      updatedAt: timestamp,
      answers: [restoredAnswer],
    }
  }).sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
}

// -----------------------------------------
// Ingestion Hooks
// -----------------------------------------

export function useIngestionJobs() {
  const { mockMode } = useMockMode()

  return useQuery({
    queryKey: [...queryKeys.ingestionJobs, mockMode] as const,
    queryFn: api.getIngestionJobs,
    refetchInterval: POLLING_INTERVALS.ingestionJob,
  })
}

export function useIngestDirectory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: IngestRequest) => api.submitIngestion(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestionJobs })
    },
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => api.uploadDocument(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestionJobs })
      queryClient.invalidateQueries({ queryKey: queryKeys.documents })
      queryClient.invalidateQueries({ queryKey: queryKeys.chunks() })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats })
      queryClient.invalidateQueries({ queryKey: queryKeys.activity })
    },
  })
}

export function useDeleteIngestionJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jobId: string) => api.deleteIngestionJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestionJobs })
      queryClient.invalidateQueries({ queryKey: queryKeys.documents })
      queryClient.invalidateQueries({ queryKey: queryKeys.chunks() })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats })
      queryClient.invalidateQueries({ queryKey: queryKeys.activity })
    },
  })
}

// -----------------------------------------
// Document Hooks
// -----------------------------------------

export function useDocuments() {
  const { mockMode } = useMockMode()

  return useQuery({
    queryKey: [...queryKeys.documents, mockMode] as const,
    queryFn: api.getDocuments,
  })
}

// -----------------------------------------
// Retrieval Hooks
// -----------------------------------------

export function useChunks(filters?: RetrievalFilter) {
  const { mockMode } = useMockMode()

  return useQuery({
    queryKey: [...queryKeys.chunks(filters), mockMode] as const,
    queryFn: () => api.getChunks(filters),
  })
}

// -----------------------------------------
// Utility Hook for File Size Formatting
// -----------------------------------------

export function useFormatFileSize() {
  return useCallback((bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }, [])
}

// -----------------------------------------
// Utility Hook for Relative Time
// -----------------------------------------

export function useRelativeTime() {
  return useCallback((date: Date): string => {
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSecs < 60) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }, [])
}
