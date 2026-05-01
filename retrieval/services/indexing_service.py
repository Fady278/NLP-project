from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from retrieval.models.embedding_model import EmbeddingModel
from retrieval.models.index_store import IndexStateStore

logger = logging.getLogger(__name__)

_VOLATILE_METADATA_KEYS = {
    "ingestion_id",
    "ingested_at",
    "last_ingested_at",
}


class IndexingService:
    def __init__(
        self,
        vectordb_client,
        embedding_client: EmbeddingModel | None = None,
        state_path: str | Path = "data/processed/index_state.sqlite3",
    ):
        self.embedding_client = embedding_client if embedding_client else EmbeddingModel()
        self.vectordb_client = vectordb_client
        self.state_store = IndexStateStore(state_path)

    def push_data_to_index(self, project, chunks, do_reset: bool = False, skip_existing: bool = False):
        del skip_existing  # local manifest diff makes this behavior the default

        project_id = project.id
        collection_name = self.vectordb_client.create_collection_name(project_id)

        if do_reset:
            self.vectordb_client.delete_collection(collection_name)
            self.state_store.reset_project(project_id)
            logger.info("Collection '%s' reset - fresh index", collection_name)

        unique_chunks = self._deduplicate_chunks(chunks)
        logger.info("Indexing Summary:")
        logger.info("  Total chunks: %d", len(chunks))
        logger.info("  Unique chunks: %d", len(unique_chunks))
        logger.info("  Mode: %s", "FRESH" if do_reset else "INCREMENTAL_MANIFEST_DIFF")

        if not unique_chunks:
            logger.info("No chunks to index for collection '%s'.", collection_name)
            return {
                "new_or_changed": 0,
                "unchanged": 0,
                "deleted": 0,
                "embedded": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            }

        self.vectordb_client.create_collection(
            collection_name,
            self.embedding_client.embedding_size
        )

        file_hashes = sorted({
            chunk.metadata.get("file_hash")
            for chunk in unique_chunks
            if chunk.metadata.get("file_hash")
        })
        previous_rows = self.state_store.get_manifest_rows(project_id, file_hashes)
        current_rows = [self._manifest_row_from_chunk(chunk) for chunk in unique_chunks]
        current_rows_by_id = {row["chunk_id"]: row for row in current_rows}

        stale_chunk_ids = sorted(set(previous_rows) - set(current_rows_by_id))
        if stale_chunk_ids:
            deleted = self.vectordb_client.delete_points(collection_name, stale_chunk_ids)
            self.state_store.delete_manifest_chunk_ids(project_id, stale_chunk_ids)
            logger.info("  Removed %d stale chunk(s).", deleted)

        unchanged_rows: list[dict[str, Any]] = []
        changed_rows: list[dict[str, Any]] = []
        for row in current_rows:
            previous = previous_rows.get(row["chunk_id"])
            if previous and self._rows_match(previous, row):
                unchanged_rows.append(row)
            else:
                changed_rows.append(row)

        vectors_by_hash, cache_stats = self._resolve_vectors(changed_rows)

        if changed_rows:
            self.vectordb_client.add_documents(
                collection_name=collection_name,
                texts=[row["text"] for row in changed_rows],
                vectors=[vectors_by_hash[row["chunk_content_hash"]] for row in changed_rows],
                metadata=[row["metadata"] for row in changed_rows],
                point_ids=[row["chunk_id"] for row in changed_rows],
            )

        self.state_store.replace_manifest_rows(project_id, file_hashes, current_rows)

        logger.info(
            "  Unchanged: %d | New/changed: %d | Deleted: %d | Embedded: %d",
            len(unchanged_rows),
            len(changed_rows),
            len(stale_chunk_ids),
            cache_stats["misses"],
        )

        return {
            "new_or_changed": len(changed_rows),
            "unchanged": len(unchanged_rows),
            "deleted": len(stale_chunk_ids),
            "embedded": cache_stats["misses"],
            "cache_hits": cache_stats["hits"],
            "cache_misses": cache_stats["misses"],
        }

    @staticmethod
    def _deduplicate_chunks(chunks) -> list:
        unique_chunks = []
        seen_chunk_ids = set()
        duplicate_ids = 0
        for chunk in chunks:
            if chunk.chunk_id in seen_chunk_ids:
                duplicate_ids += 1
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            unique_chunks.append(chunk)

        if duplicate_ids:
            logger.info("  Duplicate chunk IDs removed: %d", duplicate_ids)
        return unique_chunks

    def _manifest_row_from_chunk(self, chunk) -> dict[str, Any]:
        metadata = self._stable_metadata(chunk.metadata)
        metadata.update(
            {
                "chunk_id": chunk.chunk_id,
                "source_doc_id": chunk.source_doc_id,
                "source_path": chunk.source_path,
                "file_type": chunk.file_type,
                "page_num": chunk.page_num,
                "strategy": chunk.strategy,
                "document_group_id": metadata.get("document_group_id", chunk.source_doc_id),
                "chunk_content_hash": metadata["chunk_content_hash"],
            }
        )
        return {
            "chunk_id": chunk.chunk_id,
            "file_hash": metadata.get("file_hash"),
            "source_doc_id": chunk.source_doc_id,
            "source_path": chunk.source_path,
            "chunk_content_hash": metadata["chunk_content_hash"],
            "metadata": metadata,
            "text": chunk.text,
        }

    @staticmethod
    def _rows_match(previous: dict[str, Any], current: dict[str, Any]) -> bool:
        return (
            previous.get("chunk_content_hash") == current.get("chunk_content_hash")
            and previous.get("metadata") == current.get("metadata")
        )

    @staticmethod
    def _stable_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        stable = {
            key: value
            for key, value in dict(metadata).items()
            if key not in _VOLATILE_METADATA_KEYS
        }
        stable.pop("first_ingested_at", None)
        return stable

    def _resolve_vectors(self, rows: list[dict[str, Any]]) -> tuple[dict[str, list[float]], dict[str, int]]:
        content_hashes = list(dict.fromkeys(row["chunk_content_hash"] for row in rows))
        cached_vectors = self.state_store.get_cached_vectors(
            self.embedding_client.cache_namespace,
            content_hashes,
        )

        missing_rows = []
        missing_hashes = []
        seen_missing = set()
        for row in rows:
            content_hash = row["chunk_content_hash"]
            if content_hash in cached_vectors or content_hash in seen_missing:
                continue
            missing_rows.append(row)
            missing_hashes.append(content_hash)
            seen_missing.add(content_hash)

        if missing_rows:
            vectors = self.embedding_client.embed_batch(
                [row["text"] for row in missing_rows],
                doc_type="passage",
            )
            new_vectors = {
                content_hash: vector
                for content_hash, vector in zip(missing_hashes, vectors)
            }
            self.state_store.put_cached_vectors(self.embedding_client.cache_namespace, new_vectors)
            cached_vectors.update(new_vectors)

        return cached_vectors, {
            "hits": len(content_hashes) - len(missing_rows),
            "misses": len(missing_rows),
        }
