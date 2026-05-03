from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from api.schemas.ingest import DeleteIngestionResponse
from api.services.errors import PipelineExecutionError, ResourceNotFoundError
from api.services.system_state import ApiStateStore
from retrieval.models.index_store import IndexStateStore
from retrieval.models.vectorDB_client import VectorDBClient


class IngestionDeletionService:
    def __init__(
        self,
        *,
        processed_dir: str | Path = "data/processed",
        state_store: ApiStateStore | None = None,
    ) -> None:
        self.processed_dir = Path(processed_dir)
        self.state_store = state_store or ApiStateStore(self.processed_dir / "api_state.json")
        self.index_store = IndexStateStore(self.processed_dir / "index_state.sqlite3")
        self.project_root = Path(__file__).resolve().parents[2]

    def delete_job(self, job_id: str) -> DeleteIngestionResponse:
        job = self.state_store.get_ingestion_job(job_id)
        if job is None:
            raise ResourceNotFoundError("Ingestion job not found")

        metadata = job.get("metadata", {}) or {}
        input_path = self._resolve_path(metadata.get("input_path"))
        output_dir = Path(str(metadata.get("output_dir") or self.processed_dir))
        ingestion_id = str(metadata.get("ingestion_id") or "")
        project_id = str(metadata.get("project_id") or "")
        related_job_ids = self._collect_related_job_ids(job_id, input_path)
        targets = self._collect_targets(input_path, output_dir, ingestion_id)
        if not targets["source_paths"] and input_path.is_dir():
            fallback_paths = [path.resolve(strict=False) for path in input_path.rglob("*") if path.is_file()]
            targets["source_paths"].update(str(path) for path in fallback_paths)

        input_exists = input_path.exists()
        if not targets["source_paths"] and not targets["file_hashes"] and not input_exists:
            raise PipelineExecutionError(
                "Nothing matched this ingestion job",
                "No tracked files were found for deletion.",
            )

        removed_vectors = 0
        for file_hash in targets["file_hashes"]:
            removed_vectors += self._delete_vector_records(project_id, file_hash)

        removed_rows = self._delete_processed_rows(output_dir, targets["source_paths"], targets["file_hashes"])
        removed_snapshot_files = self._delete_snapshot_files(output_dir, ingestion_id)
        removed_raw_files = self._delete_raw_paths(targets["source_paths"])
        removed_directory = self._delete_empty_directory(input_path)

        deleted_job = self.state_store.delete_ingestion_job(job_id)
        if deleted_job is None:
            raise PipelineExecutionError("Failed to delete ingestion job", job_id)
        removed_related_jobs = 0
        for related_job_id in related_job_ids:
            if self.state_store.delete_ingestion_job(related_job_id) is not None:
                removed_related_jobs += 1

        return DeleteIngestionResponse(
            message="Ingestion data deleted",
            deleted=True,
            metadata={
                "job_id": job_id,
                "removed_raw_files": removed_raw_files,
                "removed_directory": removed_directory,
                "removed_processed_rows": removed_rows,
                "removed_snapshot_files": removed_snapshot_files,
                "removed_vector_points": removed_vectors,
                "file_name": job.get("file_name"),
                "removed_related_jobs": removed_related_jobs,
                "legacy_cleanup": not targets["file_hashes"],
            },
        )

    def _collect_targets(self, input_path: Path, output_dir: Path, ingestion_id: str) -> dict[str, set[str]]:
        file_hashes: set[str] = set()
        source_paths: set[str] = set()

        snapshot_paths = [
            output_dir / f"clean_documents__{ingestion_id}.jsonl",
            output_dir / f"chunks_sentence_window__{ingestion_id}.jsonl",
            output_dir / f"chunks_paragraph__{ingestion_id}.jsonl",
        ]
        existing_snapshot_paths = [path for path in snapshot_paths if path.exists()]

        search_paths = existing_snapshot_paths or [
            output_dir / "clean_documents.jsonl",
            output_dir / "chunks_sentence_window.jsonl",
            output_dir / "chunks_paragraph.jsonl",
        ]

        for path in search_paths:
            if not path.exists():
                continue
            for row in self._read_jsonl(path):
                source_path = str(self._resolve_path(row.get("source_path")))
                metadata = row.get("metadata", {}) or {}
                matches_source = source_path == str(input_path)
                matches_directory = input_path.is_dir() and source_path.startswith(f"{input_path}{os.sep}")
                if matches_source or matches_directory:
                    if source_path:
                        source_paths.add(source_path)
                    file_hash = metadata.get("file_hash")
                    if isinstance(file_hash, str) and file_hash:
                        file_hashes.add(file_hash)

        if input_path.is_dir() and not source_paths:
            current_files = [path.resolve(strict=False) for path in input_path.rglob("*") if path.is_file()]
            source_paths.update(str(path) for path in current_files)

            fallback_paths = [
                output_dir / "clean_documents.jsonl",
                output_dir / "chunks_sentence_window.jsonl",
                output_dir / "chunks_paragraph.jsonl",
            ]
            current_sources = set(source_paths)
            for path in fallback_paths:
                if not path.exists():
                    continue
                for row in self._read_jsonl(path):
                    source_path = str(self._resolve_path(row.get("source_path")))
                    if source_path not in current_sources:
                        continue
                    metadata = row.get("metadata", {}) or {}
                    file_hash = metadata.get("file_hash")
                    if isinstance(file_hash, str) and file_hash:
                        file_hashes.add(file_hash)

        return {
            "source_paths": source_paths,
            "file_hashes": file_hashes,
        }

    def _delete_vector_records(self, project_id: str, file_hash: str) -> int:
        if not project_id or not file_hash:
            return 0

        rows = self.index_store.list_manifest_rows_by_file_hash(project_id, file_hash)
        chunk_ids = [row["chunk_id"] for row in rows if row.get("chunk_id")]
        if not chunk_ids:
            self.index_store.delete_manifest_by_file_hash(project_id, file_hash)
            return 0

        collection_name = VectorDBClient().create_collection_name(project_id)
        vectordb_client = VectorDBClient()
        removed = vectordb_client.delete_points(collection_name, chunk_ids)
        self.index_store.delete_manifest_by_file_hash(project_id, file_hash)
        return removed

    def _delete_processed_rows(self, output_dir: Path, source_paths: set[str], file_hashes: set[str]) -> int:
        removed_rows = 0
        for path in output_dir.glob("*.jsonl"):
            rows = self._read_jsonl(path)
            if not rows:
                continue

            kept_rows: list[dict[str, Any]] = []
            before_count = len(rows)
            for row in rows:
                metadata = row.get("metadata", {}) or {}
                source_path = str(self._resolve_path(row.get("source_path")))
                file_hash = metadata.get("file_hash")
                matches_source = source_path in source_paths
                matches_hash = isinstance(file_hash, str) and file_hash in file_hashes
                if matches_source or matches_hash:
                    continue
                kept_rows.append(row)

            if len(kept_rows) == before_count:
                continue

            removed_rows += before_count - len(kept_rows)
            self._write_jsonl(path, kept_rows)

        return removed_rows

    def _delete_snapshot_files(self, output_dir: Path, ingestion_id: str) -> int:
        if not ingestion_id:
            return 0

        removed = 0
        for path in output_dir.glob(f"*__{ingestion_id}.jsonl"):
            if path.exists():
                path.unlink()
                removed += 1
        return removed

    @staticmethod
    def _delete_raw_paths(source_paths: set[str]) -> int:
        removed = 0
        for raw_path in sorted(source_paths, reverse=True):
            path = Path(raw_path)
            if not path.exists() or not path.is_file():
                continue
            path.unlink()
            removed += 1
        return removed

    @staticmethod
    def _delete_empty_directory(input_path: Path) -> bool:
        if not input_path.exists() or not input_path.is_dir():
            return False
        try:
            next(input_path.iterdir())
            return False
        except StopIteration:
            input_path.rmdir()
            return True

    def _resolve_path(self, value: object) -> Path:
        raw = str(value or "").strip()
        if not raw:
            return Path()

        path = Path(raw)
        if not path.is_absolute():
            path = self.project_root / path

        try:
            return path.resolve(strict=False)
        except OSError:
            return path

    def _collect_related_job_ids(self, job_id: str, input_path: Path) -> list[str]:
        if not input_path.is_dir():
            return []

        related_job_ids: list[str] = []
        root = f"{input_path}{os.sep}"
        for item in self.state_store.list_ingestion_jobs():
            candidate_job_id = str(item.get("id") or "")
            if not candidate_job_id or candidate_job_id == job_id:
                continue

            metadata = item.get("metadata", {}) or {}
            candidate_path = self._resolve_path(metadata.get("input_path"))
            candidate_str = str(candidate_path)
            if candidate_str.startswith(root):
                related_job_ids.append(candidate_job_id)

        return related_job_ids

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not path.exists():
            return items

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
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
