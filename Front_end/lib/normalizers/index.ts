import type {
  ActivityEvent,
  Document,
  IngestionJob,
  RetrievedChunk,
  SystemStats,
  QueryAnswer,
} from '@/lib/models/types'

function toDate(value: unknown, fallback = new Date()): Date {
  if (value instanceof Date) return value
  if (typeof value === 'string' || typeof value === 'number') {
    const parsed = new Date(value)
    if (!Number.isNaN(parsed.getTime())) return parsed
  }
  return fallback
}

function toNumber(value: unknown, fallback = 0): number {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function toStringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim().length > 0 ? value : fallback
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function normalizeChunk(raw: unknown, index = 0): RetrievedChunk {
  const data = toRecord(raw)
  const metadata = toRecord(data.metadata)
  const source =
    toStringValue(data.source) ||
    toStringValue(data.source_file) ||
    toStringValue(data.source_path) ||
    toStringValue(metadata.source_file) ||
    toStringValue(metadata.source_path) ||
    'Unknown source'

  const pageNumberRaw =
    data.pageNumber ?? data.page_num ?? data.page ?? metadata.page_num ?? metadata.page
  const pageNumber =
    pageNumberRaw === null || pageNumberRaw === undefined
      ? undefined
      : toNumber(pageNumberRaw, NaN)

  return {
    id:
      toStringValue(data.id) ||
      toStringValue(data.chunk_id) ||
      toStringValue(metadata.chunk_id) ||
      `chunk-${index}`,
    text: toStringValue(data.text) || toStringValue(data.content),
    score: toNumber(data.score ?? data.similarity, 0),
    source,
    pageNumber: Number.isNaN(pageNumber) ? undefined : pageNumber,
    section:
      toStringValue(data.section) ||
      toStringValue(data.section_title) ||
      toStringValue(metadata.section_title),
    metadata,
  }
}

export function normalizeQueryAnswer(raw: unknown): QueryAnswer {
  const data = toRecord(raw)
  const chunks = Array.isArray(data.chunks)
    ? data.chunks.map((chunk, index) => normalizeChunk(chunk, index))
    : Array.isArray(data.retrieved_context)
      ? data.retrieved_context.map((chunk, index) => normalizeChunk(chunk, index))
    : Array.isArray(data.results)
      ? data.results.map((chunk, index) => normalizeChunk(chunk, index))
      : []

  return {
    id: toStringValue(data.id) || `answer-${Date.now()}`,
    question: toStringValue(data.question) || toStringValue(data.query),
    answer: toStringValue(data.answer),
    chunks,
    timestamp: toDate(data.timestamp),
    modelUsed: toStringValue(data.modelUsed) || toStringValue(data.model_used),
    tokensUsed:
      data.tokensUsed === undefined && data.tokens_used === undefined
        ? undefined
        : toNumber(data.tokensUsed ?? data.tokens_used, 0),
    metadata: toRecord(data.metadata),
  }
}

export function normalizeIngestionJob(raw: unknown, index = 0): IngestionJob {
  const data = toRecord(raw)
  const rawStatus = toStringValue(data.status, 'queued').toLowerCase()
  const status =
    rawStatus === 'processing' || rawStatus === 'indexed' || rawStatus === 'failed'
      ? rawStatus
      : 'queued'

  return {
    id: toStringValue(data.id) || toStringValue(data.jobId) || `job-${index}`,
    fileName: toStringValue(data.fileName) || toStringValue(data.file_name) || 'Unknown file',
    fileSize: toNumber(data.fileSize ?? data.file_size, 0),
    fileType:
      toStringValue(data.fileType) ||
      toStringValue(data.file_type) ||
      toStringValue(data.mime_type) ||
      'unknown',
    status,
    progress:
      data.progress === undefined || data.progress === null
        ? undefined
        : toNumber(data.progress, 0),
    chunksCreated:
      data.chunksCreated === undefined && data.chunks_created === undefined
        ? undefined
        : toNumber(data.chunksCreated ?? data.chunks_created, 0),
    errorMessage:
      toStringValue(data.errorMessage) ||
      toStringValue(data.error_message) ||
      toStringValue(data.error),
    createdAt: toDate(data.createdAt ?? data.created_at ?? data.submittedAt),
    updatedAt: toDate(data.updatedAt ?? data.updated_at ?? data.submittedAt),
    metadata: toRecord(data.metadata),
  }
}

export function normalizeDocument(raw: unknown, index = 0): Document {
  const data = toRecord(raw)
  return {
    id: toStringValue(data.id) || toStringValue(data.doc_id) || `doc-${index}`,
    fileName:
      toStringValue(data.fileName) ||
      toStringValue(data.file_name) ||
      toStringValue(data.name) ||
      'Unknown document',
    fileType:
      toStringValue(data.fileType) ||
      toStringValue(data.file_type) ||
      toStringValue(data.type) ||
      'unknown',
    fileSize: toNumber(data.fileSize ?? data.file_size ?? data.size, 0),
    chunkCount: toNumber(data.chunkCount ?? data.chunk_count ?? data.total_chunks, 0),
    indexedAt: toDate(data.indexedAt ?? data.indexed_at ?? data.created_at),
    metadata: toRecord(data.metadata),
  }
}

export function normalizeStats(raw: unknown): SystemStats {
  const data = toRecord(raw)
  const health = toStringValue(data.retrievalHealth || data.retrieval_health, 'offline')
  const normalizedHealth =
    health === 'healthy' || health === 'degraded' || health === 'offline'
      ? health
      : 'offline'

  return {
    totalDocuments: toNumber(data.totalDocuments ?? data.total_documents ?? data.documents_count, 0),
    totalChunks: toNumber(data.totalChunks ?? data.total_chunks ?? data.chunks_count, 0),
    retrievalHealth: normalizedHealth,
    lastIngestionAt:
      data.lastIngestionAt || data.last_ingestion_at
        ? toDate(data.lastIngestionAt ?? data.last_ingestion_at)
        : undefined,
    avgRetrievalLatencyMs:
      data.avgRetrievalLatencyMs === undefined && data.avg_retrieval_latency_ms === undefined
        ? undefined
        : toNumber(data.avgRetrievalLatencyMs ?? data.avg_retrieval_latency_ms, 0),
  }
}

export function normalizeActivityEvent(raw: unknown, index = 0): ActivityEvent {
  const data = toRecord(raw)
  const type = toStringValue(data.type, 'query')
  const normalizedType =
    type === 'query' || type === 'ingestion' || type === 'error' ? type : 'query'

  return {
    id: toStringValue(data.id) || `activity-${index}`,
    type: normalizedType,
    description:
      toStringValue(data.description) ||
      toStringValue(data.message) ||
      toStringValue(data.title) ||
      'Activity event',
    timestamp: toDate(data.timestamp ?? data.created_at ?? data.updated_at),
    metadata: toRecord(data.metadata),
  }
}

export function normalizeChunksResponse(raw: unknown): { chunks: RetrievedChunk[]; total: number } {
  const data = toRecord(raw)
  const rawChunks = Array.isArray(data.chunks)
    ? data.chunks
    : Array.isArray(data.results)
      ? data.results
      : []

  return {
    chunks: rawChunks.map((chunk, index) => normalizeChunk(chunk, index)),
    total: toNumber(data.total ?? data.totalCount ?? data.total_count ?? rawChunks.length, rawChunks.length),
  }
}
