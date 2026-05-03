from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from api.schemas.system import (
    ActivityEventResponse,
    ChunksResponse,
    DocumentResponse,
    IngestionJobResponse,
    StatsResponse,
)
from api.services.system_state import ApiStateStore


class SystemDataService:
    def __init__(
        self,
        *,
        processed_dir: str | Path = "data/processed",
        raw_dir: str | Path = "data/raw",
        state_store: ApiStateStore | None = None,
    ) -> None:
        self.processed_dir = Path(processed_dir)
        self.raw_dir = Path(raw_dir)
        self.state_store = state_store or ApiStateStore(self.processed_dir / "api_state.json")
        self.project_root = Path(__file__).resolve().parents[2]

    def get_stats(self) -> StatsResponse:
        documents = self.get_documents()
        chunks_payload = self.get_chunks()
        activities = self.state_store.list_activities()

        retrieval_health = "offline"
        if chunks_payload.total > 0:
            retrieval_health = "healthy"
        elif documents:
            retrieval_health = "degraded"

        last_ingestion_at = max((doc.indexed_at for doc in documents if doc.indexed_at), default=None)

        query_latencies = []
        for event in activities:
            metadata = event.get("metadata", {})
            if event.get("type") == "query" and isinstance(metadata, dict):
                latency = metadata.get("latency_ms")
                if isinstance(latency, (int, float)):
                    query_latencies.append(float(latency))

        avg_latency = round(sum(query_latencies) / len(query_latencies), 2) if query_latencies else None
        return StatsResponse(
            total_documents=len(documents),
            total_chunks=chunks_payload.total,
            retrieval_health=retrieval_health,
            last_ingestion_at=last_ingestion_at,
            avg_retrieval_latency_ms=avg_latency,
        )

    def get_activity(self) -> list[ActivityEventResponse]:
        return [ActivityEventResponse(**item) for item in self.state_store.list_activities()]

    def get_ingestion_jobs(self) -> list[IngestionJobResponse]:
        return [IngestionJobResponse(**item) for item in self.state_store.list_ingestion_jobs()]

    def get_ingestion_job(self, job_id: str) -> IngestionJobResponse | None:
        for item in self.state_store.list_ingestion_jobs():
            if item.get("id") == job_id:
                return IngestionJobResponse(**item)
        return None

    def get_documents(self) -> list[DocumentResponse]:
        docs = self._read_jsonl(self.processed_dir / "clean_documents.jsonl")
        chunks = self._read_jsonl(self._find_chunks_file())

        chunk_counts: dict[str, int] = {}
        for chunk in chunks:
            source_path = str(chunk.get("source_path") or "")
            if source_path:
                chunk_counts[source_path] = chunk_counts.get(source_path, 0) + 1

        grouped: dict[str, dict[str, Any]] = {}
        for doc in docs:
            source_path = str(doc.get("source_path") or "")
            if not source_path:
                continue
            metadata = doc.get("metadata", {}) or {}
            existing = grouped.setdefault(
                source_path,
                {
                    "id": str(doc.get("doc_id") or Path(source_path).stem),
                    "file_name": Path(source_path).name,
                    "file_type": str(doc.get("file_type") or Path(source_path).suffix.lstrip(".")),
                    "file_size": self._safe_file_size(source_path),
                    "chunk_count": chunk_counts.get(source_path, 0),
                    "indexed_at": metadata.get("last_ingested_at") or metadata.get("ingested_at"),
                    "metadata": {
                        "source_path": source_path,
                        "detected_lang": doc.get("detected_lang"),
                        "is_arabic": doc.get("is_arabic"),
                    },
                },
            )
            indexed_at = metadata.get("last_ingested_at") or metadata.get("ingested_at")
            if indexed_at and (not existing["indexed_at"] or indexed_at > existing["indexed_at"]):
                existing["indexed_at"] = indexed_at

        return [DocumentResponse(**item) for item in grouped.values()]

    def get_document(self, document_id: str) -> DocumentResponse | None:
        for item in self.get_documents():
            if item.id == document_id:
                return item
        return None

    def get_chunks(
        self,
        *,
        source: str | None = None,
        file_types: list[str] | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
    ) -> ChunksResponse:
        chunks = self._read_jsonl(self._find_chunks_file())
        items: list[dict[str, Any]] = []
        normalized_file_types = {item.lower() for item in file_types} if file_types else None
        for index, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {}) or {}
            source_path = str(chunk.get("source_path") or metadata.get("source_path") or "")
            file_type = str(chunk.get("file_type") or metadata.get("file_type") or Path(source_path).suffix.lstrip("."))
            score = self._derive_chunk_score(chunk)

            if source and source.lower() not in source_path.lower():
                continue
            if normalized_file_types and file_type.lower() not in normalized_file_types:
                continue
            if min_score is not None and score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue

            items.append(
                {
                    "id": chunk.get("chunk_id") or f"chunk-{index}",
                    "text": chunk.get("text", ""),
                    "score": score,
                    "source": source_path,
                    "page_num": chunk.get("page_num"),
                    "metadata": metadata,
                }
            )

        return ChunksResponse(chunks=items, total=len(items))

    def record_query_activity(
        self,
        *,
        question: str,
        project_id: str,
        top_k: int,
        retrieved_count: int,
        latency_ms: float,
        answer: str | None = None,
        retrieved_context: list[dict[str, Any]] | None = None,
        model_used: str | None = None,
        response_metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> None:
        self.state_store.record_activity(
            event_type="query",
            description=f'Query: "{question}"',
            metadata={
                "project_id": project_id,
                "top_k": top_k,
                "retrieved_count": retrieved_count,
                "latency_ms": round(latency_ms, 2),
                "question": question,
                "answer": answer,
                "retrieved_context": [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in (retrieved_context or [])
                ],
                "model_used": model_used,
                "response_metadata": response_metadata or {},
            },
            timestamp=timestamp,
        )

    def record_ingestion_activity(
        self,
        *,
        file_name: str,
        chunks_created: int,
        project_id: str | None,
    ) -> None:
        self.state_store.record_activity(
            event_type="ingestion",
            description=f"Indexed: {file_name} ({chunks_created} chunks)",
            metadata={
                "project_id": project_id,
                "chunks_created": chunks_created,
            },
        )

    def save_ingestion_job(self, payload: dict[str, Any]) -> IngestionJobResponse:
        metadata = payload.get("metadata", {}) or {}
        existing = self._find_matching_ingestion_job(payload, metadata)
        if existing:
            payload["id"] = existing.get("id", payload.get("id"))
            payload["created_at"] = existing.get("created_at", payload.get("created_at"))
        saved = self.state_store.save_ingestion_job(payload)
        return IngestionJobResponse(**saved)

    def _find_matching_ingestion_job(self, payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any] | None:
        project_id = str(metadata.get("project_id") or "")
        candidate_type = str(payload.get("file_type") or "")
        candidate_input_path = self._normalize_path(metadata.get("input_path"))
        candidate_hashes = {
            str(item)
            for item in (metadata.get("file_hashes") or [])
            if str(item).strip()
        }
        candidate_sources = {
            self._normalize_path(item)
            for item in (metadata.get("source_paths") or [])
            if str(item).strip()
        }

        for job in self.state_store.list_ingestion_jobs():
            job_metadata = job.get("metadata", {}) or {}
            if str(job_metadata.get("project_id") or "") != project_id:
                continue

            job_type = str(job.get("file_type") or "")
            if job_type != candidate_type:
                continue

            job_input_path = self._normalize_path(job_metadata.get("input_path"))
            if candidate_type == "directory" and candidate_input_path and job_input_path == candidate_input_path:
                return job

            job_hashes = {
                str(item)
                for item in (job_metadata.get("file_hashes") or [])
                if str(item).strip()
            }
            if candidate_hashes and job_hashes and candidate_hashes.intersection(job_hashes):
                return job

            job_sources = {
                self._normalize_path(item)
                for item in (job_metadata.get("source_paths") or [])
                if str(item).strip()
            }
            if candidate_sources and job_sources and candidate_sources.intersection(job_sources):
                return job

        return None

    def _normalize_path(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""

        path = Path(raw)
        if not path.is_absolute():
            path = self.project_root / path

        try:
            return str(path.resolve(strict=False))
        except OSError:
            return str(path)

    def _find_chunks_file(self) -> Path:
        preferred = self.processed_dir / "chunks_sentence_window.jsonl"
        if preferred.exists():
            return preferred

        candidates = sorted(self.processed_dir.glob("chunks_*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else self.processed_dir / "chunks_sentence_window.jsonl"

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    items.append(parsed)
        return items

    @staticmethod
    def _derive_chunk_score(chunk: dict[str, Any]) -> float:
        token_count = int(chunk.get("token_count") or 0)
        if token_count <= 0:
            return 0.0
        normalized = min(0.99, max(0.1, token_count / 250))
        return round(normalized, 4)

    @staticmethod
    def _safe_file_size(source_path: str) -> int:
        try:
            return Path(source_path).stat().st_size
        except OSError:
            return 0
