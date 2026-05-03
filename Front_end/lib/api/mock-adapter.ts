// ============================================
// Mock API Adapter
// Simulates API responses with realistic delays
// ============================================

import type {
  QueryAnswer,
  QueryRequest,
  IngestionJob,
  Document,
  SystemStats,
  ActivityEvent,
  RetrievedChunk,
  RetrievalFilter,
} from '@/lib/models/types'
import {
  MOCK_ANSWERS,
  MOCK_CHUNKS,
  MOCK_INGESTION_JOBS,
  MOCK_DOCUMENTS,
  MOCK_STATS,
  MOCK_ACTIVITY,
} from '@/lib/mocks/fixtures'

// Simulate network delay
const delay = (min = 300, max = 800) =>
  new Promise((resolve) =>
    setTimeout(resolve, Math.random() * (max - min) + min)
  )

// Generate a unique ID
const generateId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

// -----------------------------------------
// Query Operations
// -----------------------------------------

export async function mockQuery(request: QueryRequest): Promise<QueryAnswer> {
  await delay(500, 1500)

  // Simulate selecting relevant chunks based on question
  const shuffledChunks = [...MOCK_CHUNKS]
    .sort(() => Math.random() - 0.5)
    .slice(0, request.topK || 4)
    .sort((a, b) => b.score - a.score)

  const answer: QueryAnswer = {
    id: generateId(),
    question: request.question,
    answer: generateMockAnswer(request.question),
    chunks: shuffledChunks,
    timestamp: new Date(),
    modelUsed: 'gpt-4-turbo',
    tokensUsed: Math.floor(Math.random() * 1500) + 500,
  }

  return answer
}

function generateMockAnswer(question: string): string {
  const lowerQuestion = question.toLowerCase()

  if (lowerQuestion.includes('rag') || lowerQuestion.includes('retrieval')) {
    return 'RAG (Retrieval-Augmented Generation) is an AI architecture that enhances large language models by combining them with external knowledge retrieval. When a user asks a question, the system first searches a knowledge base using vector similarity to find relevant documents or chunks. These retrieved pieces of context are then provided to the LLM along with the original question, allowing it to generate more accurate, up-to-date, and grounded responses.'
  }

  if (lowerQuestion.includes('embedding') || lowerQuestion.includes('vector')) {
    return 'Vector embeddings transform text into dense numerical representations in high-dimensional space, where semantically similar texts are positioned close together. This enables semantic search by comparing query embeddings against document embeddings using distance metrics like cosine similarity.'
  }

  if (lowerQuestion.includes('chunk')) {
    return 'Chunking strategies significantly impact retrieval quality. Common approaches include fixed-size chunks (e.g., 512 tokens), sentence-based splitting, and semantic chunking that respects document structure. The optimal strategy depends on your document types and query patterns.'
  }

  return `Based on the retrieved context, here is the answer to your question: "${question}"\n\nThe system found several relevant passages in the indexed documents that address this topic. The retrieved evidence suggests that this is a complex topic with multiple facets. Please review the source chunks for detailed information.`
}

// -----------------------------------------
// Ingestion Operations
// -----------------------------------------

// Store for simulating job progress
const jobStore = new Map<string, IngestionJob>()

export async function mockUpload(file: File): Promise<IngestionJob> {
  await delay(200, 500)

  const job: IngestionJob = {
    id: generateId(),
    fileName: file.name,
    fileSize: file.size,
    fileType: file.name.split('.').pop() || 'unknown',
    status: 'queued',
    progress: 0,
    createdAt: new Date(),
    updatedAt: new Date(),
  }

  jobStore.set(job.id, job)

  // Simulate job progression
  simulateJobProgress(job.id)

  return job
}

function simulateJobProgress(jobId: string) {
  const job = jobStore.get(jobId)
  if (!job) return

  // Random failure ~10% of the time
  const willFail = Math.random() < 0.1

  let progress = 0
  const interval = setInterval(() => {
    progress += Math.floor(Math.random() * 20) + 10

    if (willFail && progress > 50) {
      job.status = 'failed'
      job.errorMessage = 'Simulated processing error for testing'
      job.updatedAt = new Date()
      clearInterval(interval)
      return
    }

    if (progress >= 100) {
      job.status = 'indexed'
      job.progress = 100
      job.chunksCreated = Math.floor(Math.random() * 200) + 20
      job.updatedAt = new Date()
      clearInterval(interval)
    } else {
      job.status = 'processing'
      job.progress = Math.min(progress, 99)
      job.updatedAt = new Date()
    }
  }, 1000)
}

export async function mockGetIngestionJobs(): Promise<IngestionJob[]> {
  await delay()

  // Combine stored jobs with mock fixtures
  const storedJobs = Array.from(jobStore.values())
  return [...storedJobs, ...MOCK_INGESTION_JOBS].sort(
    (a, b) => b.createdAt.getTime() - a.createdAt.getTime()
  )
}

export async function mockGetIngestionJob(id: string): Promise<IngestionJob | null> {
  await delay(100, 300)

  // Check stored jobs first
  const storedJob = jobStore.get(id)
  if (storedJob) return storedJob

  // Fall back to fixtures
  return MOCK_INGESTION_JOBS.find((job) => job.id === id) || null
}

// -----------------------------------------
// Document Operations
// -----------------------------------------

export async function mockGetDocuments(): Promise<Document[]> {
  await delay()
  return MOCK_DOCUMENTS
}

export async function mockGetDocument(id: string): Promise<Document | null> {
  await delay(100, 300)
  return MOCK_DOCUMENTS.find((doc) => doc.id === id) || null
}

// -----------------------------------------
// Retrieval Operations
// -----------------------------------------

export async function mockGetChunks(
  filters?: RetrievalFilter
): Promise<{ chunks: RetrievedChunk[]; total: number }> {
  await delay()

  let filtered = [...MOCK_CHUNKS]

  if (filters?.sourceFile) {
    filtered = filtered.filter((c) =>
      c.source.toLowerCase().includes(filters.sourceFile!.toLowerCase())
    )
  }

  if (filters?.fileType?.length) {
    filtered = filtered.filter((c) =>
      filters.fileType!.some((type) => c.source.endsWith(`.${type}`))
    )
  }

  if (filters?.minScore !== undefined) {
    filtered = filtered.filter((c) => c.score >= filters.minScore!)
  }

  if (filters?.maxScore !== undefined) {
    filtered = filtered.filter((c) => c.score <= filters.maxScore!)
  }

  return {
    chunks: filtered.sort((a, b) => b.score - a.score),
    total: filtered.length,
  }
}

// -----------------------------------------
// Stats Operations
// -----------------------------------------

export async function mockGetStats(): Promise<SystemStats> {
  await delay(100, 300)
  return {
    ...MOCK_STATS,
    // Add some variance
    avgRetrievalLatencyMs: Math.floor(Math.random() * 50) + 100,
  }
}

export async function mockGetActivity(): Promise<ActivityEvent[]> {
  await delay()
  return MOCK_ACTIVITY
}

// -----------------------------------------
// Query History (client-side only)
// -----------------------------------------

export function getQueryHistory(): QueryAnswer[] {
  return MOCK_ANSWERS
}
