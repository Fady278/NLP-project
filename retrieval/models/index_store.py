from __future__ import annotations

import contextlib
import json
import sqlite3
from array import array
from pathlib import Path
from typing import Any


class IndexStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _initialize(self) -> None:
        with contextlib.closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    model_key TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    vector_blob BLOB NOT NULL,
                    PRIMARY KEY (model_key, content_hash)
                );

                CREATE TABLE IF NOT EXISTS chunk_manifest (
                    project_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    file_hash TEXT,
                    source_doc_id TEXT,
                    source_path TEXT NOT NULL,
                    chunk_content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, chunk_id)
                );

                CREATE INDEX IF NOT EXISTS idx_chunk_manifest_project_file
                ON chunk_manifest(project_id, file_hash);

                CREATE INDEX IF NOT EXISTS idx_chunk_manifest_project_doc
                ON chunk_manifest(project_id, source_doc_id);
                """
            )
            conn.commit()

    def get_cached_vectors(self, model_key: str, content_hashes: list[str]) -> dict[str, list[float]]:
        if not content_hashes:
            return {}

        placeholders = ",".join("?" for _ in content_hashes)
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT content_hash, vector_blob
                FROM embedding_cache
                WHERE model_key = ?
                  AND content_hash IN ({placeholders})
                """,
                [model_key, *content_hashes],
            ).fetchall()

        return {
            row["content_hash"]: self._blob_to_vector(row["vector_blob"])
            for row in rows
        }

    def put_cached_vectors(self, model_key: str, vectors_by_hash: dict[str, list[float]]) -> None:
        if not vectors_by_hash:
            return

        with contextlib.closing(self._connect()) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO embedding_cache (model_key, content_hash, vector_blob)
                VALUES (?, ?, ?)
                """,
                [
                    (model_key, content_hash, self._vector_to_blob(vector))
                    for content_hash, vector in vectors_by_hash.items()
                ],
            )
            conn.commit()

    def get_manifest_rows(self, project_id: str, file_hashes: list[str]) -> dict[str, dict[str, Any]]:
        if not file_hashes:
            return {}

        placeholders = ",".join("?" for _ in file_hashes)
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT chunk_id, file_hash, source_doc_id, source_path, chunk_content_hash, metadata_json
                FROM chunk_manifest
                WHERE project_id = ?
                  AND file_hash IN ({placeholders})
                """,
                [project_id, *file_hashes],
            ).fetchall()

        manifests: dict[str, dict[str, Any]] = {}
        for row in rows:
            manifests[row["chunk_id"]] = {
                "chunk_id": row["chunk_id"],
                "file_hash": row["file_hash"],
                "source_doc_id": row["source_doc_id"],
                "source_path": row["source_path"],
                "chunk_content_hash": row["chunk_content_hash"],
                "metadata": json.loads(row["metadata_json"]),
            }
        return manifests

    def replace_manifest_rows(
        self,
        project_id: str,
        file_hashes: list[str],
        rows: list[dict[str, Any]],
    ) -> None:
        with contextlib.closing(self._connect()) as conn:
            if file_hashes:
                placeholders = ",".join("?" for _ in file_hashes)
                conn.execute(
                    f"""
                    DELETE FROM chunk_manifest
                    WHERE project_id = ?
                      AND file_hash IN ({placeholders})
                    """,
                    [project_id, *file_hashes],
                )

            conn.executemany(
                """
                INSERT INTO chunk_manifest (
                    project_id,
                    chunk_id,
                    file_hash,
                    source_doc_id,
                    source_path,
                    chunk_content_hash,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        project_id,
                        row["chunk_id"],
                        row.get("file_hash"),
                        row.get("source_doc_id"),
                        row["source_path"],
                        row["chunk_content_hash"],
                        json.dumps(row["metadata"], ensure_ascii=False),
                    )
                    for row in rows
                ],
            )
            conn.commit()

    def delete_manifest_chunk_ids(self, project_id: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return

        placeholders = ",".join("?" for _ in chunk_ids)
        with contextlib.closing(self._connect()) as conn:
            conn.execute(
                f"""
                DELETE FROM chunk_manifest
                WHERE project_id = ?
                  AND chunk_id IN ({placeholders})
                """,
                [project_id, *chunk_ids],
            )
            conn.commit()

    def list_manifest_rows_by_file_hash(self, project_id: str, file_hash: str) -> list[dict[str, Any]]:
        if not file_hash:
            return []

        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, file_hash, source_doc_id, source_path, chunk_content_hash, metadata_json
                FROM chunk_manifest
                WHERE project_id = ?
                  AND file_hash = ?
                """,
                [project_id, file_hash],
            ).fetchall()

        return [
            {
                "chunk_id": row["chunk_id"],
                "file_hash": row["file_hash"],
                "source_doc_id": row["source_doc_id"],
                "source_path": row["source_path"],
                "chunk_content_hash": row["chunk_content_hash"],
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def delete_manifest_by_file_hash(self, project_id: str, file_hash: str) -> None:
        if not file_hash:
            return

        with contextlib.closing(self._connect()) as conn:
            conn.execute(
                """
                DELETE FROM chunk_manifest
                WHERE project_id = ?
                  AND file_hash = ?
                """,
                [project_id, file_hash],
            )
            conn.commit()

    def reset_project(self, project_id: str) -> None:
        with contextlib.closing(self._connect()) as conn:
            conn.execute(
                "DELETE FROM chunk_manifest WHERE project_id = ?",
                [project_id],
            )
            conn.commit()

    @staticmethod
    def _vector_to_blob(vector: list[float]) -> bytes:
        return array("f", vector).tobytes()

    @staticmethod
    def _blob_to_vector(blob: bytes) -> list[float]:
        values = array("f")
        values.frombytes(blob)
        return values.tolist()
