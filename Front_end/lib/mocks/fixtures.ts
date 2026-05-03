// ============================================
// Mock Data Fixtures for RAG Console
// ============================================

import type {
  QueryAnswer,
  RetrievedChunk,
  IngestionJob,
  Document,
  SystemStats,
  ActivityEvent,
} from '@/lib/models/types'

// -----------------------------------------
// Sample Chunks with Varied Scores
// -----------------------------------------

export const MOCK_CHUNKS: RetrievedChunk[] = [
  {
    id: 'chunk-1',
    text: 'RAG (Retrieval-Augmented Generation) combines the power of large language models with external knowledge retrieval. This approach allows LLMs to access up-to-date information beyond their training data, significantly improving accuracy for domain-specific questions.',
    score: 0.95,
    source: 'rag-architecture-guide.pdf',
    pageNumber: 12,
    section: 'Introduction to RAG',
    metadata: { author: 'Technical Team', version: '2.1' },
  },
  {
    id: 'chunk-2',
    text: 'Vector embeddings represent text as dense numerical vectors in high-dimensional space. Similar texts have vectors that are close together, enabling semantic search capabilities that go beyond simple keyword matching.',
    score: 0.89,
    source: 'embeddings-explained.md',
    section: 'Vector Representations',
    metadata: { category: 'fundamentals' },
  },
  {
    id: 'chunk-3',
    text: 'Chunking strategies significantly impact retrieval quality. Common approaches include fixed-size chunks, sentence-based splitting, and semantic chunking. The optimal strategy depends on document structure and query patterns.',
    score: 0.82,
    source: 'best-practices.pdf',
    pageNumber: 34,
    section: 'Chunking Strategies',
  },
  {
    id: 'chunk-4',
    text: 'The retrieval pipeline typically includes: 1) Query embedding generation, 2) Approximate nearest neighbor search, 3) Re-ranking with cross-encoders, 4) Context assembly for the LLM prompt.',
    score: 0.76,
    source: 'rag-architecture-guide.pdf',
    pageNumber: 28,
    section: 'Retrieval Pipeline',
  },
  {
    id: 'chunk-5',
    text: 'Hybrid search combines dense vector retrieval with sparse keyword methods like BM25. This approach captures both semantic similarity and exact keyword matches, often outperforming either method alone.',
    score: 0.71,
    source: 'hybrid-search-patterns.docx',
    section: 'Hybrid Approaches',
  },
  {
    id: 'chunk-6',
    text: 'Evaluation metrics for RAG systems include: retrieval precision/recall, answer accuracy, faithfulness (grounding), and latency. Regular evaluation helps identify degradation and optimization opportunities.',
    score: 0.65,
    source: 'evaluation-guide.pdf',
    pageNumber: 8,
    section: 'Metrics Overview',
  },
  {
    id: 'chunk-7',
    text: 'Document ingestion involves parsing, cleaning, chunking, embedding, and indexing. Each step requires careful configuration to maintain document structure and maximize retrieval relevance.',
    score: 0.58,
    source: 'ingestion-pipeline.md',
    section: 'Pipeline Overview',
  },
  {
    id: 'chunk-8',
    text: 'Context window limitations require careful chunk selection. Strategies include score thresholding, maximum chunk count, and dynamic context assembly based on query complexity.',
    score: 0.52,
    source: 'best-practices.pdf',
    pageNumber: 45,
    section: 'Context Management',
  },
  {
    id: 'chunk-9',
    text: 'Re-ranking models like cross-encoders provide more accurate relevance scores but are computationally expensive. They are typically applied to a candidate set from initial retrieval.',
    score: 0.48,
    source: 'reranking-guide.html',
    section: 'Re-ranking Strategies',
  },
  {
    id: 'chunk-10',
    text: 'Metadata filtering allows narrowing search scope before vector similarity. Common filters include document type, date range, author, and custom tags.',
    score: 0.45,
    source: 'metadata-strategies.txt',
    section: 'Filtering Techniques',
  },
]

// -----------------------------------------
// Sample Query Answers
// -----------------------------------------

export const MOCK_ANSWERS: QueryAnswer[] = [
  {
    id: 'answer-1',
    question: 'What is RAG and how does it work?',
    answer: 'RAG (Retrieval-Augmented Generation) is an AI architecture that enhances large language models by combining them with external knowledge retrieval. When a user asks a question, the system first searches a knowledge base using vector similarity to find relevant documents or chunks. These retrieved pieces of context are then provided to the LLM along with the original question, allowing it to generate more accurate, up-to-date, and grounded responses. This approach overcomes the limitation of LLMs only knowing information from their training data.',
    chunks: MOCK_CHUNKS.slice(0, 4),
    timestamp: new Date(Date.now() - 300000), // 5 minutes ago
    modelUsed: 'gpt-4-turbo',
    tokensUsed: 1247,
  },
  {
    id: 'answer-2',
    question: 'How do vector embeddings enable semantic search?',
    answer: 'Vector embeddings transform text into dense numerical representations in high-dimensional space, where semantically similar texts are positioned close together. This enables semantic search by comparing query embeddings against document embeddings using distance metrics like cosine similarity. Unlike keyword matching, semantic search understands meaning - for example, finding documents about "automobiles" when searching for "cars".',
    chunks: MOCK_CHUNKS.slice(1, 3),
    timestamp: new Date(Date.now() - 600000), // 10 minutes ago
    modelUsed: 'gpt-4-turbo',
    tokensUsed: 892,
  },
]

// -----------------------------------------
// Sample Ingestion Jobs
// -----------------------------------------

export const MOCK_INGESTION_JOBS: IngestionJob[] = [
  {
    id: 'job-1',
    fileName: 'quarterly-report-q4-2024.pdf',
    fileSize: 2457600, // ~2.4 MB
    fileType: 'pdf',
    status: 'indexed',
    progress: 100,
    chunksCreated: 156,
    createdAt: new Date(Date.now() - 3600000), // 1 hour ago
    updatedAt: new Date(Date.now() - 3500000),
  },
  {
    id: 'job-2',
    fileName: 'technical-documentation.md',
    fileSize: 524288, // ~512 KB
    fileType: 'md',
    status: 'processing',
    progress: 67,
    createdAt: new Date(Date.now() - 180000), // 3 minutes ago
    updatedAt: new Date(Date.now() - 30000),
  },
  {
    id: 'job-3',
    fileName: 'api-reference.html',
    fileSize: 1048576, // ~1 MB
    fileType: 'html',
    status: 'queued',
    createdAt: new Date(Date.now() - 120000), // 2 minutes ago
    updatedAt: new Date(Date.now() - 120000),
  },
  {
    id: 'job-4',
    fileName: 'legacy-docs.docx',
    fileSize: 3145728, // ~3 MB
    fileType: 'docx',
    status: 'failed',
    errorMessage: 'Document parsing failed: unsupported format version',
    createdAt: new Date(Date.now() - 7200000), // 2 hours ago
    updatedAt: new Date(Date.now() - 7100000),
  },
  {
    id: 'job-5',
    fileName: 'meeting-notes.txt',
    fileSize: 102400, // ~100 KB
    fileType: 'txt',
    status: 'indexed',
    progress: 100,
    chunksCreated: 23,
    createdAt: new Date(Date.now() - 86400000), // 1 day ago
    updatedAt: new Date(Date.now() - 86300000),
  },
]

// -----------------------------------------
// Sample Documents
// -----------------------------------------

export const MOCK_DOCUMENTS: Document[] = [
  {
    id: 'doc-1',
    fileName: 'rag-architecture-guide.pdf',
    fileType: 'pdf',
    fileSize: 4194304, // ~4 MB
    chunkCount: 234,
    indexedAt: new Date(Date.now() - 604800000), // 1 week ago
    metadata: { author: 'Technical Team', version: '2.1' },
  },
  {
    id: 'doc-2',
    fileName: 'embeddings-explained.md',
    fileType: 'md',
    fileSize: 262144, // ~256 KB
    chunkCount: 45,
    indexedAt: new Date(Date.now() - 432000000), // 5 days ago
    metadata: { category: 'fundamentals' },
  },
  {
    id: 'doc-3',
    fileName: 'best-practices.pdf',
    fileType: 'pdf',
    fileSize: 2097152, // ~2 MB
    chunkCount: 189,
    indexedAt: new Date(Date.now() - 259200000), // 3 days ago
  },
  {
    id: 'doc-4',
    fileName: 'quarterly-report-q4-2024.pdf',
    fileType: 'pdf',
    fileSize: 2457600,
    chunkCount: 156,
    indexedAt: new Date(Date.now() - 3600000),
  },
  {
    id: 'doc-5',
    fileName: 'meeting-notes.txt',
    fileType: 'txt',
    fileSize: 102400,
    chunkCount: 23,
    indexedAt: new Date(Date.now() - 86400000),
  },
]

// -----------------------------------------
// System Stats
// -----------------------------------------

export const MOCK_STATS: SystemStats = {
  totalDocuments: 47,
  totalChunks: 3842,
  retrievalHealth: 'healthy',
  lastIngestionAt: new Date(Date.now() - 3600000),
  avgRetrievalLatencyMs: 127,
}

// -----------------------------------------
// Activity Feed
// -----------------------------------------

export const MOCK_ACTIVITY: ActivityEvent[] = [
  {
    id: 'activity-1',
    type: 'query',
    description: 'Query: "What is RAG and how does it work?"',
    timestamp: new Date(Date.now() - 300000),
    metadata: { chunks: 4, latencyMs: 145 },
  },
  {
    id: 'activity-2',
    type: 'ingestion',
    description: 'Indexed: quarterly-report-q4-2024.pdf (156 chunks)',
    timestamp: new Date(Date.now() - 3500000),
  },
  {
    id: 'activity-3',
    type: 'query',
    description: 'Query: "How do vector embeddings enable semantic search?"',
    timestamp: new Date(Date.now() - 600000),
    metadata: { chunks: 2, latencyMs: 98 },
  },
  {
    id: 'activity-4',
    type: 'error',
    description: 'Ingestion failed: legacy-docs.docx - unsupported format',
    timestamp: new Date(Date.now() - 7100000),
  },
  {
    id: 'activity-5',
    type: 'ingestion',
    description: 'Indexed: meeting-notes.txt (23 chunks)',
    timestamp: new Date(Date.now() - 86300000),
  },
  {
    id: 'activity-6',
    type: 'query',
    description: 'Query: "Best practices for document chunking"',
    timestamp: new Date(Date.now() - 172800000),
    metadata: { chunks: 3, latencyMs: 112 },
  },
  {
    id: 'activity-7',
    type: 'ingestion',
    description: 'Indexed: best-practices.pdf (189 chunks)',
    timestamp: new Date(Date.now() - 259200000),
  },
  {
    id: 'activity-8',
    type: 'ingestion',
    description: 'Indexed: embeddings-explained.md (45 chunks)',
    timestamp: new Date(Date.now() - 432000000),
  },
  {
    id: 'activity-9',
    type: 'query',
    description: 'Query: "Explain hybrid search approaches"',
    timestamp: new Date(Date.now() - 518400000),
    metadata: { chunks: 5, latencyMs: 167 },
  },
  {
    id: 'activity-10',
    type: 'ingestion',
    description: 'Indexed: rag-architecture-guide.pdf (234 chunks)',
    timestamp: new Date(Date.now() - 604800000),
  },
]
