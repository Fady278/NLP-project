from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, TYPE_CHECKING

from api.schemas.query import QueryResponse
from api.services.errors import ApiServiceError, PipelineExecutionError
from api.services.llm_factory import create_llm_service
from api.services.query_enhancer import QueryEnhancer
from api.services.system_service import SystemDataService

if TYPE_CHECKING:
    from api.services.llm_base import BaseLLMService
    from retrieval.services.rag_service import RAGService
    from retrieval.services.retrieval_service import RetrievalService


class QueryApplicationService:
    _TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u0600-\u06FF]+")
    _SEMANTIC_VARIANT_SCORE_FLOOR = 0.76
    _SEMANTIC_FALLBACK_SCORE_FLOOR = 0.68
    _LEXICAL_SCORE_FLOOR = 0.72
    _LEXICAL_MIN_OVERLAP = 2

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        rag_service: RAGService | None = None,
        llm_service: BaseLLMService | None = None,
        system_data_service: SystemDataService | None = None,
        processed_dir: str | Path = "data/processed",
    ) -> None:
        self.llm_service = llm_service or create_llm_service()
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
        self.query_enhancer = QueryEnhancer(self.llm_service, processed_dir=self.processed_dir)
        self.expand_adjacent_chunks = False

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
            initial_chunks = self.retrieval_service.search(
                project_id=project_id,
                query=query,
                top_k=top_k,
            )
            query_variants = self.query_enhancer.variants_for_query(
                query,
                conversation_context=conversation_context,
                retrieval_results=initial_chunks,
            )
            chunks = self._retrieve_with_variants(
                project_id=project_id,
                query_variants=query_variants,
                top_k=top_k,
            )
            if self.expand_adjacent_chunks:
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
                    "query_variants": query_variants,
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
                "query_variants": query_variants,
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

    def _retrieve_with_variants(
        self,
        *,
        project_id: str,
        query_variants: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not query_variants:
            return []

        merged: list[dict[str, Any]] = []
        best_by_chunk_id: dict[str, dict[str, Any]] = {}
        fallback_rows: list[dict[str, Any]] = []
        accepted_semantic = 0
        best_semantic_score = 0.0

        for index, variant in enumerate(query_variants):
            results = self.retrieval_service.search(
                project_id=project_id,
                query=variant,
                top_k=top_k,
                dedup=False,
            )
            top_score = self._top_result_score(results)
            if top_score is not None:
                best_semantic_score = max(best_semantic_score, top_score)

            if index > 0 and (top_score is None or top_score < self._SEMANTIC_VARIANT_SCORE_FLOOR):
                continue

            if results:
                accepted_semantic += 1

            for row in results:
                metadata = row.get("metadata", {}) or {}
                chunk_id = metadata.get("chunk_id")
                if isinstance(chunk_id, str) and chunk_id:
                    existing = best_by_chunk_id.get(chunk_id)
                    score = row.get("score")
                    existing_score = existing.get("score") if isinstance(existing, dict) else None
                    if existing is None or (
                        isinstance(score, (int, float))
                        and (not isinstance(existing_score, (int, float)) or score > existing_score)
                    ):
                        best_by_chunk_id[chunk_id] = row
                else:
                    fallback_rows.append(row)

        if accepted_semantic == 0 or best_semantic_score < self._SEMANTIC_FALLBACK_SCORE_FLOOR:
            for variant in query_variants[:1]:
                lexical_results = self._search_local_chunks(variant, top_k=top_k)
                for row in lexical_results:
                    metadata = row.get("metadata", {}) or {}
                    chunk_id = metadata.get("chunk_id")
                    if isinstance(chunk_id, str) and chunk_id:
                        existing = best_by_chunk_id.get(chunk_id)
                        if existing is None or row.get("score", 0) > existing.get("score", 0):
                            best_by_chunk_id[chunk_id] = row
                    else:
                        fallback_rows.append(row)

        merged.extend(best_by_chunk_id.values())
        merged.extend(fallback_rows)
        merged.sort(key=lambda item: item.get("score", 0), reverse=True)
        return self.retrieval_service._post_process(merged, top_k, dedup=True)

    def _search_local_chunks(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        tokens = self._tokenize_for_match(query)
        if not tokens:
            return []

        rows = self._load_chunk_rows()
        scored: list[tuple[float, dict[str, Any]]] = []
        query_text = query.casefold()

        for row in rows:
            text = str(row.get("text", ""))
            text_tokens = self._tokenize_for_match(text)
            if not text_tokens:
                continue

            overlap = len(tokens.intersection(text_tokens))
            if overlap < self._LEXICAL_MIN_OVERLAP:
                continue

            coverage = overlap / max(1, len(tokens))
            phrase_match = query_text in text.casefold()
            if not phrase_match and coverage < 0.55:
                continue

            phrase_bonus = 0.1 if phrase_match else 0.0
            score = min(0.9, 0.42 + (coverage * 0.36) + phrase_bonus)
            if score < self._LEXICAL_SCORE_FLOOR:
                continue
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._row_to_chunk(row, base_score=score)
            for score, row in scored[: max(top_k, 3)]
        ]

    @classmethod
    def _tokenize_for_match(cls, text: str) -> set[str]:
        tokens = {
            match.group(0).casefold()
            for match in cls._TOKEN_RE.finditer(text)
            if len(match.group(0)) > 1
        }
        return tokens

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
            metadata = dict(chunk.get("metadata", {}) or {})
            if "page_num" in metadata and "page_label" not in metadata:
                page_num = metadata.get("page_num")
                if isinstance(page_num, int) and page_num >= 0:
                    metadata["page_label"] = str(page_num + 1)
            serialized.append(
                {
                    "text": chunk.get("text", ""),
                    "metadata": metadata,
                    "score": chunk.get("score"),
                }
            )
        return serialized

    @staticmethod
    def _top_result_score(results: list[dict[str, Any]]) -> float | None:
        if not results:
            return None
        score = results[0].get("score")
        return float(score) if isinstance(score, (int, float)) else None

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
