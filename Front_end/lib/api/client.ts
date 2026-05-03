// ============================================
// Centralized API Client
// Prefers real backend data and uses mock-mode fallback when enabled.
// ============================================

import { API_CONFIG, ENDPOINTS, getMockMode } from '@/lib/config/api'
import type {
  QueryAnswer,
  QueryRequest,
  IngestionJob,
  IngestRequest,
  Document,
  SystemStats,
  ActivityEvent,
  RetrievedChunk,
  RetrievalFilter,
  ApiResponse,
} from '@/lib/models/types'
import * as mockAdapter from './mock-adapter'
import {
  normalizeActivityEvent,
  normalizeChunksResponse,
  normalizeDocument,
  normalizeIngestionJob,
  normalizeQueryAnswer,
  normalizeStats,
} from '@/lib/normalizers'

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const url = `${API_CONFIG.baseUrl}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      let details = `API Error: ${response.status} ${response.statusText}`
      try {
        const errorBody = await response.json()
        if (errorBody?.error) {
          details = errorBody.details ? `${errorBody.error}: ${errorBody.details}` : errorBody.error
        }
      } catch {
        // Ignore non-JSON error bodies.
      }
      throw new Error(details)
    }

    const data = await response.json()
    return { data, success: true }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    console.warn(`API request failed: ${endpoint}`, message)
    return { data: null as T, success: false, error: message }
  }
}

function normalizeArray<T>(items: unknown, normalizer: (item: unknown, index: number) => T): T[] {
  return Array.isArray(items) ? items.map((item, index) => normalizer(item, index)) : []
}

function hasUsableValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    if (typeof record.total === 'number' && record.total > 0) {
      return true
    }
    return Object.keys(record).length > 0
  }
  return value !== null && value !== undefined
}

async function resolveWithMockMode<T>(
  realRequest: () => Promise<T | null>,
  mockRequest: () => Promise<T>,
  merge?: (realData: T, mockData: T) => T
): Promise<T> {
  const mockMode = getMockMode()

  if (!mockMode) {
    const realData = await realRequest()
    if (realData === null) {
      throw new Error('Real backend response was empty')
    }
    return realData
  }

  // MOCK MODE ENABLED
  if (merge) {
    try {
      const realData = await realRequest()
      if (realData !== null && hasUsableValue(realData)) {
        const mockData = await mockRequest()
        return merge(realData, mockData)
      }
    } catch {}
    return mockRequest()
  }

  // No merge (single items or actions)
  // Try mock data first
  const mockData = await mockRequest()
  if (mockData !== null && mockData !== undefined) {
    return mockData
  }

  // Fallback to real data if mock data is explicitly null (e.g. getById not found in mocks)
  try {
    const realData = await realRequest()
    if (realData !== null) {
      return realData
    }
  } catch {}

  throw new Error('Not found in mock data and real backend fallback failed')
}

function mergeStats(realData: SystemStats, mockData: SystemStats): SystemStats {
  const latestIngestion =
    realData.lastIngestionAt && mockData.lastIngestionAt
      ? new Date(
          Math.max(
            realData.lastIngestionAt.getTime(),
            mockData.lastIngestionAt.getTime()
          )
        )
      : realData.lastIngestionAt ?? mockData.lastIngestionAt

  return {
    totalDocuments: Math.max(realData.totalDocuments, mockData.totalDocuments),
    totalChunks: Math.max(realData.totalChunks, mockData.totalChunks),
    retrievalHealth:
      realData.retrievalHealth === 'offline'
        ? mockData.retrievalHealth
        : realData.retrievalHealth,
    lastIngestionAt: latestIngestion,
    avgRetrievalLatencyMs:
      realData.avgRetrievalLatencyMs ?? mockData.avgRetrievalLatencyMs,
  }
}

export async function submitQuery(request: QueryRequest): Promise<QueryAnswer> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<QueryAnswer>(ENDPOINTS.query, {
        method: 'POST',
        body: JSON.stringify({
          project_id: request.projectId || API_CONFIG.defaultProjectId,
          query: request.question,
          top_k: request.topK ?? 5,
          prompt_version: request.promptVersion ?? 'strict',
          conversation_context: request.conversationContext,
        }),
      })

      if (!response.success) {
        throw new Error(response.error || 'Query failed')
      }

      const normalized = normalizeQueryAnswer(response.data)
      return {
        ...normalized,
        question: normalized.question || request.question,
      }
    },
    () => mockAdapter.mockQuery(request)
  )
}

export async function submitIngestion(request: IngestRequest): Promise<IngestionJob> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<Record<string, unknown>>(ENDPOINTS.ingest, {
        method: 'POST',
        body: JSON.stringify({
          input_dir: request.inputDir,
          project_id: request.projectId || API_CONFIG.defaultProjectId,
          output_dir: request.outputDir || 'data/processed',
          chunk_strategy: request.chunkStrategy || 'sentence_window',
          keep_diacritics: request.keepDiacritics ?? false,
          index_to_vectordb: request.indexToVectorDb ?? true,
          reset_vectordb: request.resetVectorDb ?? false,
          skip_existing: request.skipExisting ?? true,
        }),
      })

      if (!response.success) {
        throw new Error(response.error || 'Ingestion failed')
      }

      const metadata =
        response.data && typeof response.data.metadata === 'object' && response.data.metadata !== null
          ? (response.data.metadata as Record<string, unknown>)
          : {}

      return normalizeIngestionJob({
        id: metadata.ingestion_id || `ingest-${Date.now()}`,
        file_name: request.inputDir,
        file_type: 'directory',
        status: 'indexed',
        progress: 100,
        chunks_created: typeof metadata.chunks_created === 'number' ? metadata.chunks_created : undefined,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    },
    async () => {
      const mockFile = new File([''], request.inputDir || 'input-dir.txt')
      return mockAdapter.mockUpload(mockFile)
    }
  )
}

export async function uploadDocument(file: File, projectId?: string): Promise<IngestionJob> {
  return resolveWithMockMode(
    async () => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('project_id', projectId || API_CONFIG.defaultProjectId)
      formData.append('index_to_vectordb', 'true')
      formData.append('chunk_strategy', 'sentence_window')
      formData.append('skip_existing', 'true')

      const url = `${API_CONFIG.baseUrl}${ENDPOINTS.ingest}`
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let details = `Upload failed: ${response.status}`
        try {
          const body = await response.json()
          if (body?.error) {
            details = body.details ? `${body.error}: ${body.details}` : body.error
          }
        } catch {
          // Ignore non-JSON upload error bodies.
        }
        throw new Error(details)
      }

      const payload = await response.json()
      const metadata =
        payload && typeof payload.metadata === 'object' && payload.metadata !== null
          ? (payload.metadata as Record<string, unknown>)
          : {}

      return normalizeIngestionJob({
        id: metadata.ingestion_id || `ingest-${Date.now()}`,
        file_name: file.name,
        file_size: file.size,
        file_type: file.name.split('.').pop() || 'unknown',
        status: 'indexed',
        progress: 100,
        chunks_created: typeof metadata.chunks_created === 'number' ? metadata.chunks_created : undefined,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    },
    () => mockAdapter.mockUpload(file)
  )
}

export async function getIngestionJobs(): Promise<IngestionJob[]> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<IngestionJob[]>(ENDPOINTS.ingestionJobs)
      return response.success ? normalizeArray(response.data, normalizeIngestionJob) : []
    },
    () => mockAdapter.mockGetIngestionJobs(),
    (realData, mockData) => [...realData, ...mockData]
  )
}

export async function getIngestionJob(id: string): Promise<IngestionJob | null> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<IngestionJob>(ENDPOINTS.ingestionJob(id))
      return response.success ? normalizeIngestionJob(response.data) : null
    },
    async () => mockAdapter.mockGetIngestionJob(id)
  )
}

export async function deleteIngestionJob(id: string): Promise<{ deleted: boolean; message: string }> {
  const mockMode = getMockMode()
  if (mockMode) {
    return {
      deleted: false,
      message: 'Disable Mock Mode to delete real uploaded files.',
    }
  }

  const response = await apiFetch<{ deleted: boolean; message: string }>(ENDPOINTS.ingestionJob(id), {
    method: 'DELETE',
  })

  if (!response.success) {
    throw new Error(response.error || 'Delete failed')
  }

  return response.data
}

export async function getDocuments(): Promise<Document[]> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<Document[]>(ENDPOINTS.documents)
      return response.success ? normalizeArray(response.data, normalizeDocument) : []
    },
    () => mockAdapter.mockGetDocuments(),
    (realData, mockData) => [...realData, ...mockData]
  )
}

export async function getDocument(id: string): Promise<Document | null> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<Document>(ENDPOINTS.document(id))
      return response.success ? normalizeDocument(response.data) : null
    },
    async () => mockAdapter.mockGetDocument(id)
  )
}

export async function getChunks(filters?: RetrievalFilter): Promise<{ chunks: RetrievedChunk[]; total: number }> {
  return resolveWithMockMode(
    async () => {
      const params = new URLSearchParams()
      if (filters?.sourceFile) params.set('source', filters.sourceFile)
      if (filters?.fileType?.length) params.set('types', filters.fileType.join(','))
      if (filters?.minScore !== undefined) params.set('minScore', String(filters.minScore))
      if (filters?.maxScore !== undefined) params.set('maxScore', String(filters.maxScore))

      const endpoint = `${ENDPOINTS.chunks}?${params.toString()}`
      const response = await apiFetch<{ chunks: RetrievedChunk[]; total: number }>(endpoint)
      return response.success ? normalizeChunksResponse(response.data) : { chunks: [], total: 0 }
    },
    () => mockAdapter.mockGetChunks(filters),
    (realData, mockData) => ({
      chunks: [...realData.chunks, ...mockData.chunks],
      total: realData.total + mockData.total,
    })
  )
}

export async function getStats(): Promise<SystemStats> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<SystemStats>(ENDPOINTS.stats)
      return response.success
        ? normalizeStats(response.data)
        : {
            totalDocuments: 0,
            totalChunks: 0,
            retrievalHealth: 'offline',
          }
    },
    () => mockAdapter.mockGetStats(),
    mergeStats
  )
}

export async function getActivity(): Promise<ActivityEvent[]> {
  return resolveWithMockMode(
    async () => {
      const response = await apiFetch<ActivityEvent[]>(ENDPOINTS.activity)
      return response.success ? normalizeArray(response.data, normalizeActivityEvent) : []
    },
    () => mockAdapter.mockGetActivity(),
    (realData, mockData) => [...realData, ...mockData]
  )
}

export function getQueryHistory(): QueryAnswer[] {
  return getMockMode() ? mockAdapter.getQueryHistory() : []
}
