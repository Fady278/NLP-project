from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, TYPE_CHECKING

from api.schemas.query import QueryResponse
from api.services.cerebras_llm import CerebrasLLMService
from api.services.errors import ApiServiceError, PipelineExecutionError
from api.services.system_service import SystemDataService

if TYPE_CHECKING:
    from retrieval.services.rag_service import RAGService
    from retrieval.services.retrieval_service import RetrievalService


class QueryApplicationService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        rag_service: RAGService | None = None,
        llm_service: CerebrasLLMService | None = None,
        system_data_service: SystemDataService | None = None,
        processed_dir: str | Path = "data/processed",
    ) -> None:
        self.llm_service = llm_service or CerebrasLLMService()
        if retrieval_service is None:
            from retrieval.models.vectorDB_client import VectorDBClient
            from retrieval.services.retrieval_service import RetrievalService

            retrieval_service = RetrievalService(VectorDBClient())
        self.retrieval_service = retrieval_service

        if rag_service is None:
            from retrieval.services.rag_service import RAGService

            rag_service = RAGService(self.retrieval_service, self.llm_service)
        self.rag_service = rag_service
        self.system_data_service = system_data_service or SystemDataService()
        self.processed_dir = Path(processed_dir)

    def execute(
        self,
        *,
        project_id: str,
        query: str,
        conversation_context: str | None = None,
        top_k: int = 5,
        prompt_version: str = "strict",
    ) -> QueryResponse:
        started_at = perf_counter()
        try:
            chunks = self.retrieval_service.search(
                project_id=project_id,
                query=query,
                top_k=top_k,
            )
            chunks = self._expand_with_adjacent_chunks(chunks)
        except Exception as exc:  # noqa: BLE001
            raise PipelineExecutionError(
                "Retrieval pipeline failed",
                str(exc),
            ) from exc

        latency_ms = (perf_counter() - started_at) * 1000

        if not chunks:
            empty_response = QueryResponse(
                question=query,
                answer="I don't know",
                sources=[],
                retrieved_context=[],
                metadata={
                    "project_id": project_id,
                    "top_k": top_k,
                    "prompt_version": prompt_version,
                    "retrieved_count": 0,
                    **self.llm_service.metadata(),
                },
                timestamp=datetime.utcnow().isoformat(),
                model_used=self.llm_service.model,
            )
            self.system_data_service.record_query_activity(
                question=query,
                project_id=project_id,
                top_k=top_k,
                retrieved_count=0,
                latency_ms=latency_ms,
                answer=empty_response.answer,
                retrieved_context=[],
                model_used=empty_response.model_used,
                response_metadata=empty_response.metadata,
                timestamp=empty_response.timestamp,
            )
            return empty_response

        try:
            normalized_prompt_version = self.rag_service._normalize_prompt_version(prompt_version)
            context = self.rag_service._build_context(chunks)
            prompt_question = self._build_prompt_question(query, conversation_context)
            prompt = self.rag_service._build_prompt(prompt_question, context, version=normalized_prompt_version)
            answer = self.llm_service.generate(prompt)
            sources = self.rag_service._extract_sources(chunks)
        except ApiServiceError as exc:
            raise PipelineExecutionError(
                "Answer generation failed",
                exc.details or exc.message,
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise PipelineExecutionError(
                "Answer generation failed",
                str(exc),
            ) from exc

        response = QueryResponse(
            question=query,
            answer=answer,
            sources=sources,
            retrieved_context=self._serialize_chunks(chunks),
            metadata={
                "project_id": project_id,
                "top_k": top_k,
                "prompt_version": normalized_prompt_version,
                "retrieved_count": len(chunks),
                "latency_ms": round(latency_ms, 2),
                "context_used": bool(conversation_context),
                **self.llm_service.metadata(),
            },
            timestamp=datetime.utcnow().isoformat(),
            model_used=self.llm_service.model,
        )
        self.system_data_service.record_query_activity(
            question=query,
            project_id=project_id,
            top_k=top_k,
            retrieved_count=len(chunks),
            latency_ms=latency_ms,
            answer=response.answer,
            retrieved_context=response.retrieved_context,
            model_used=response.model_used,
            response_metadata=response.metadata,
            timestamp=response.timestamp,
        )
        return response

    @staticmethod
    def _build_prompt_question(query: str, conversation_context: str | None) -> str:
        if not conversation_context:
            return query

        return (
            "Conversation context from earlier turns:\n"
            f"{conversation_context}\n\n"
            "Current user question:\n"
            f"{query}"
        )

    @staticmethod
    def _serialize_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for chunk in chunks:
            serialized.append(
                {
                    "text": chunk.get("text", ""),
                    "metadata": chunk.get("metadata", {}) or {},
                    "score": chunk.get("score"),
                }
            )
        return serialized

    def _expand_with_adjacent_chunks(self, chunks: list[dict[str, Any]], *, neighbor_window: int = 1) -> list[dict[str, Any]]:
        if not chunks:
            return chunks

        chunk_rows = self._load_chunk_rows()
        if not chunk_rows:
            return chunks

        lookup: dict[tuple[str, int], dict[str, Any]] = {}
        for row in chunk_rows:
            metadata = row.get("metadata", {}) or {}
            chunk_index = metadata.get("chunk_index")
            if not isinstance(chunk_index, int):
                continue
            document_key = (
                metadata.get("document_group_id")
                or row.get("source_doc_id")
                or metadata.get("source_doc_id")
            )
            if not document_key:
                continue
            lookup[(str(document_key), chunk_index)] = row

        expanded: list[dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()

        for chunk in chunks:
            self._append_unique_chunk(expanded, seen_chunk_ids, chunk)

            metadata = chunk.get("metadata", {}) or {}
            chunk_index = metadata.get("chunk_index")
            document_key = metadata.get("document_group_id") or metadata.get("source_doc_id")
            if not isinstance(chunk_index, int) or not document_key:
                continue

            for offset in range(1, neighbor_window + 1):
                for neighbor_index in (chunk_index - offset, chunk_index + offset):
                    neighbor_row = lookup.get((str(document_key), neighbor_index))
                    if not neighbor_row:
                        continue
                    neighbor_chunk = self._row_to_chunk(neighbor_row, base_score=chunk.get("score"))
                    self._append_unique_chunk(expanded, seen_chunk_ids, neighbor_chunk)

        return expanded

    def _load_chunk_rows(self) -> list[dict[str, Any]]:
        chunk_file = self._find_chunk_file()
        if not chunk_file.exists():
            return []

        rows: list[dict[str, Any]] = []
        with chunk_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
        return rows

    def _find_chunk_file(self) -> Path:
        preferred = self.processed_dir / "chunks_sentence_window.jsonl"
        if preferred.exists():
            return preferred

        candidates = sorted(
            self.processed_dir.glob("chunks_*.jsonl"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else preferred

    @staticmethod
    def _row_to_chunk(row: dict[str, Any], *, base_score: float | None) -> dict[str, Any]:
        metadata = dict(row.get("metadata", {}) or {})
        metadata.setdefault("source_doc_id", row.get("source_doc_id"))
        metadata.setdefault("source_path", row.get("source_path"))
        metadata.setdefault("page_num", row.get("page_num"))
        metadata.setdefault("file_type", row.get("file_type"))
        metadata.setdefault("chunk_id", row.get("chunk_id"))
        return {
            "text": row.get("text", ""),
            "metadata": metadata,
            "score": base_score if isinstance(base_score, (int, float)) else 0.0,
        }

    @staticmethod
    def _append_unique_chunk(
        items: list[dict[str, Any]],
        seen_chunk_ids: set[str],
        chunk: dict[str, Any],
    ) -> None:
        metadata = chunk.get("metadata", {}) or {}
        chunk_id = metadata.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id in seen_chunk_ids:
            return
        if isinstance(chunk_id, str):
            seen_chunk_ids.add(chunk_id)
        items.append(chunk)
