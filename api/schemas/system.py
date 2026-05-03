from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ActivityEventResponse(BaseModel):
    id: str
    type: Literal["query", "ingestion", "error"]
    description: str
    timestamp: str
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(extra="forbid")


class DocumentResponse(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_size: int
    chunk_count: int
    indexed_at: str | None = None
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(extra="forbid")


class ChunksResponse(BaseModel):
    chunks: list[dict[str, Any]]
    total: int

    model_config = ConfigDict(extra="forbid")


class StatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    retrieval_health: Literal["healthy", "degraded", "offline"]
    last_ingestion_at: str | None = None
    avg_retrieval_latency_ms: float | None = None

    model_config = ConfigDict(extra="forbid")


class IngestionJobResponse(BaseModel):
    id: str
    file_name: str
    file_size: int
    file_type: str
    status: Literal["queued", "processing", "indexed", "failed"]
    progress: int | None = None
    chunks_created: int | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(extra="forbid")
