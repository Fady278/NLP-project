from __future__ import annotations

import hashlib

from retrieval.models.embedding_model import EmbeddingModel


class RetrievalService:
    def __init__(
        self,
        vectordb_client,
        embedding_client: EmbeddingModel | None = None,
        max_chunks_per_doc: int | None = None,
        oversample_factor: float = 2.0,
    ):
        self.embedding_client = embedding_client if embedding_client else EmbeddingModel()
        self.vectordb_client = vectordb_client
        self.max_chunks_per_doc = max_chunks_per_doc
        self.oversample_factor = max(1.0, oversample_factor)

    def search(
        self,
        project_id,
        query: str,
        top_k: int = 10,
        metadata_filter: dict | None = None,
        dedup: bool = True,
    ):
        collection_name = self.vectordb_client.create_collection_name(project_id)
        query_vector = self.embedding_client.embed(text=query, doc_type="query")
        request_k = max(top_k, int(round(top_k * self.oversample_factor)))

        results = self.vectordb_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=request_k,
            metadata_filter=metadata_filter,
        )

        if not dedup and self.max_chunks_per_doc is None:
            return results[:top_k]

        return self._post_process(results, top_k, dedup=dedup)

    def _post_process(self, results: list, top_k: int, dedup: bool) -> list:
        filtered = []
        seen_chunk_ids = set()
        seen_content_hashes = set()
        doc_counts: dict[str, int] = {}

        for result in results:
            metadata = result.get("metadata", {}) or {}
            chunk_id = metadata.get("chunk_id")
            content_hash = (
                metadata.get("chunk_content_hash")
                or hashlib.sha256(result.get("text", "").encode("utf-8")).hexdigest()
            )

            if dedup:
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                if content_hash in seen_content_hashes:
                    continue

            document_key = metadata.get("document_group_id") or metadata.get("source_doc_id")
            if self.max_chunks_per_doc is not None and document_key:
                count = doc_counts.get(document_key, 0)
                if count >= self.max_chunks_per_doc:
                    continue
                doc_counts[document_key] = count + 1

            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            if dedup:
                seen_content_hashes.add(content_hash)

            filtered.append(result)
            if len(filtered) >= top_k:
                break

        return filtered
