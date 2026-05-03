// ============================================
// RAG Console - TypeScript Type Definitions
// ============================================

// -----------------------------------------
// Query & Answer Types
// -----------------------------------------

export interface RetrievedChunk {
  id: string
  text: string
  score: number
  source: string
  pageNumber?: number
  section?: string
  metadata?: Record<string, unknown>
}

export interface QueryAnswer {
  id: string
  question: string
  answer: string
  chunks: RetrievedChunk[]
  timestamp: Date
  modelUsed?: string
  tokensUsed?: number
  metadata?: Record<string, unknown>
  status?: 'pending' | 'success' | 'error'
}

export interface ChatSession {
  id: string
  title: string
  createdAt: Date
  updatedAt: Date
  answers: QueryAnswer[]
}

export interface QueryRequest {
  question: string
  projectId?: string
  topK?: number
  promptVersion?: 'simple' | 'strict'
  conversationContext?: string
}

// -----------------------------------------
// Ingestion Types
// -----------------------------------------

export type IngestionStatus = 'queued' | 'processing' | 'indexed' | 'failed'

export interface IngestionJob {
  id: string
  fileName: string
  fileSize: number
  fileType: string
  status: IngestionStatus
  progress?: number
  chunksCreated?: number
  errorMessage?: string
  createdAt: Date
  updatedAt: Date
  metadata?: Record<string, unknown>
}

export interface UploadRequest {
  file: File
  metadata?: Record<string, unknown>
}

export interface IngestRequest {
  inputDir: string
  projectId?: string
  outputDir?: string
  chunkStrategy?: 'paragraph' | 'sentence_window'
  keepDiacritics?: boolean
  indexToVectorDb?: boolean
  resetVectorDb?: boolean
  skipExisting?: boolean
}

// -----------------------------------------
// Document Types
// -----------------------------------------

export interface Document {
  id: string
  fileName: string
  fileType: string
  fileSize: number
  chunkCount: number
  indexedAt: Date
  metadata?: Record<string, unknown>
}

// -----------------------------------------
// Dashboard / Stats Types
// -----------------------------------------

export interface SystemStats {
  totalDocuments: number
  totalChunks: number
  retrievalHealth: 'healthy' | 'degraded' | 'offline'
  lastIngestionAt?: Date
  avgRetrievalLatencyMs?: number
}

export interface ActivityEvent {
  id: string
  type: 'query' | 'ingestion' | 'error'
  description: string
  timestamp: Date
  metadata?: Record<string, unknown>
}

// -----------------------------------------
// Retrieval Inspection Types
// -----------------------------------------

export interface RetrievalFilter {
  sourceFile?: string
  fileType?: string[]
  minScore?: number
  maxScore?: number
}

export interface RetrievalResult {
  chunks: RetrievedChunk[]
  totalCount: number
  filters: RetrievalFilter
}

// -----------------------------------------
// API Response Wrappers
// -----------------------------------------

export interface ApiResponse<T> {
  data: T
  success: boolean
  error?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}
