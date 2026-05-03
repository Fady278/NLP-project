// ============================================
// API Configuration
// ============================================

export const API_CONFIG = {
  baseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.VITE_API_BASE_URL ||
    process.env.VITE_API_URL ||
    'http://localhost:8000',
  defaultMockMode:
    (process.env.NEXT_PUBLIC_USE_MOCKS ??
      process.env.VITE_USE_MOCKS ??
      'true') !== 'false',
  defaultProjectId:
    process.env.NEXT_PUBLIC_PROJECT_ID ||
    process.env.VITE_PROJECT_ID ||
    'demo-project',
  timeout: 30000,
} as const

export const MOCK_MODE_STORAGE_KEY = 'rag-console-mock-mode'
export const CHAT_SESSIONS_STORAGE_KEY = 'rag-console-chat-sessions'
export const PENDING_CHAT_QUESTION_STORAGE_KEY = 'rag-console-pending-chat-question'

export function getMockMode(): boolean {
  if (typeof window === 'undefined') {
    return API_CONFIG.defaultMockMode
  }
  const stored = window.localStorage.getItem(MOCK_MODE_STORAGE_KEY)
  if (stored === 'true') return true
  if (stored === 'false') return false
  return API_CONFIG.defaultMockMode
}

export function setMockMode(value: boolean): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(MOCK_MODE_STORAGE_KEY, String(value))
  window.dispatchEvent(new CustomEvent('rag-console-mock-mode-change', { detail: value }))
}

export function setPendingChatQuestion(value: string): void {
  if (typeof window === 'undefined') return
  const normalized = value.trim()
  if (!normalized) return
  window.sessionStorage.setItem(PENDING_CHAT_QUESTION_STORAGE_KEY, normalized)
}

export function consumePendingChatQuestion(): string {
  if (typeof window === 'undefined') return ''
  const value = window.sessionStorage.getItem(PENDING_CHAT_QUESTION_STORAGE_KEY) || ''
  if (value) {
    window.sessionStorage.removeItem(PENDING_CHAT_QUESTION_STORAGE_KEY)
  }
  return value
}

export const ENDPOINTS = {
  query: process.env.NEXT_PUBLIC_QUERY_ENDPOINT || '/query',
  ingest: process.env.NEXT_PUBLIC_INGEST_ENDPOINT || '/ingest',
  ingestionJobs: process.env.NEXT_PUBLIC_INGESTION_JOBS_ENDPOINT || '/ingest/jobs',
  ingestionJob: (id: string) =>
    `${process.env.NEXT_PUBLIC_INGESTION_JOB_BASE || '/ingest/jobs'}/${id}`,
  documents: process.env.NEXT_PUBLIC_DOCUMENTS_ENDPOINT || '/documents',
  document: (id: string) =>
    `${process.env.NEXT_PUBLIC_DOCUMENT_BASE || '/documents'}/${id}`,
  retrieval: process.env.NEXT_PUBLIC_RETRIEVAL_ENDPOINT || '/retrieval/results',
  chunks: process.env.NEXT_PUBLIC_CHUNKS_ENDPOINT || '/chunks',
  stats: process.env.NEXT_PUBLIC_STATS_ENDPOINT || '/stats',
  activity: process.env.NEXT_PUBLIC_ACTIVITY_ENDPOINT || '/activity',
} as const

export const POLLING_INTERVALS = {
  ingestionJob: 2000,
  stats: 30000,
  activity: 10000,
} as const
