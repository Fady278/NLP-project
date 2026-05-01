"""
Preprocessing Pipeline
-----------------------
The entry-point that wires loaders → cleaner → output together.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from preprocessing.chunking import chunk_documents, save_chunks
from preprocessing.cleaners.text_cleaner import TextCleaner
from preprocessing.loaders.registry import get_loader, supported_extensions
from preprocessing.models.document import CleanDocument, save_documents
from dataclasses import dataclass
from datetime import datetime
import uuid

@dataclass
class DummyProject:
    id: str
    ingestion_id: str = ""



logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    def __init__(
        self,
        output_dir: str | Path = "data/processed",
        project_id: str | None = None,
        min_words: int = 5,
        chunk_strategy: str = "sentence_window",
        index_to_vectordb: bool = False,
        reset_vectordb: bool = False,
        skip_existing: bool = False,
        **cleaner_kwargs,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_id = project_id
        self.min_words = min_words
        self.chunk_strategy = chunk_strategy
        self.index_to_vectordb = index_to_vectordb
        self.reset_vectordb = reset_vectordb
        self.skip_existing = skip_existing
        self.cleaner = TextCleaner(**cleaner_kwargs)
        self.ingestion_id = uuid.uuid4().hex[:16]
        self.ingested_at = datetime.utcnow().isoformat()

    def _snapshot_path(self, base_name: str) -> Path:
        stem, suffix = Path(base_name).stem, Path(base_name).suffix
        return self.output_dir / f"{stem}__{self.ingestion_id}{suffix}"

    def run(self, file_paths: list[str | Path]) -> list[CleanDocument]:
        all_docs: list[CleanDocument] = []
        stats = {"files": 0, "raw_pages": 0, "clean_docs": 0, "skipped": 0}
        seen_file_hashes: set[str] = set()

        for path in file_paths:
            path = Path(path)
            try:
                loader = get_loader(path)
            except (ValueError, FileNotFoundError) as exc:
                logger.warning("Skipping '%s': %s", path.name, exc)
                stats["skipped"] += 1
                continue

            try:
                file_hash = loader.file_hash
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping '%s': could not compute file hash: %s", path.name, exc)
                stats["skipped"] += 1
                continue

            if file_hash in seen_file_hashes:
                logger.info("Skipping duplicate file '%s' (file_hash=%s).", path.name, file_hash)
                stats["skipped"] += 1
                continue
            seen_file_hashes.add(file_hash)

            try:
                raw_docs = loader.load()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping '%s': loader failed: %s", path.name, exc)
                stats["skipped"] += 1
                continue

            stats["files"] += 1
            stats["raw_pages"] += len(raw_docs)

            for raw in raw_docs:
                clean = self.cleaner.clean(raw)
                if clean.is_empty(min_words=self.min_words):
                    logger.debug(
                        "Dropping near-empty doc %s (page %d, %d words).",
                        path.name,
                        raw.page_num,
                        clean.word_count,
                    )
                    stats["skipped"] += 1
                    continue
                all_docs.append(clean)
                stats["clean_docs"] += 1

        for doc in all_docs:
            doc.metadata.setdefault("first_ingested_at", self.ingested_at)
            doc.metadata["last_ingested_at"] = self.ingested_at
            doc.metadata.setdefault("ingestion_id", self.ingestion_id)
            doc.metadata.setdefault("ingested_at", self.ingested_at)

        chunks = chunk_documents(all_docs, strategy=self.chunk_strategy)
        for chunk in chunks:
            chunk.metadata.setdefault("ingestion_id", self.ingestion_id)
            chunk.metadata.setdefault("ingested_at", self.ingested_at)
            chunk.metadata.setdefault("first_ingested_at", self.ingested_at)
            chunk.metadata["last_ingested_at"] = self.ingested_at
            chunk.metadata.setdefault("document_group_id", chunk.source_doc_id)
        output_path = self.output_dir / "clean_documents.jsonl"
        chunk_path = self.output_dir / f"chunks_{self.chunk_strategy}.jsonl"
        output_snapshot_path = self._snapshot_path(output_path.name)
        chunk_snapshot_path = self._snapshot_path(chunk_path.name)

        save_documents(all_docs, output_snapshot_path)
        save_chunks(chunks, chunk_snapshot_path)

        if self.index_to_vectordb:
            if not self.project_id:
                raise ValueError("project_id is required when index_to_vectordb=True.")
            try:
                from retrieval.models.vectorDB_client import VectorDBClient
                from retrieval.services.indexing_service import IndexingService
                from retrieval.models.embedding_model import EmbeddingModel

                vectordb_client = VectorDBClient()
                embedding_client = EmbeddingModel()
                indexing_service = IndexingService(
                    vectordb_client,
                    embedding_client,
                    state_path=self.output_dir / "index_state.sqlite3",
                )
                indexing_service.push_data_to_index(
                    project=DummyProject(id=self.project_id, ingestion_id=self.ingestion_id),
                    chunks=chunks,
                    do_reset=self.reset_vectordb,
                    skip_existing=self.skip_existing,
                )
                logger.info("Vector DB indexing complete.")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Vector DB indexing failed: %s", exc)
                logger.warning(
                    "Canonical JSONL outputs were left untouched because indexing did not complete. "
                    "Fresh snapshots were written to %s and %s.",
                    output_snapshot_path,
                    chunk_snapshot_path,
                )
                self._print_summary(stats, all_docs, len(chunks))
                return all_docs

        save_documents(all_docs, output_path)
        save_chunks(chunks, chunk_path)

        logger.info(
            "Pipeline complete — files: %d | raw pages: %d | clean docs: %d | skipped: %d → saved to %s, %s, %s and %s",
            stats["files"],
            stats["raw_pages"],
            stats["clean_docs"],
            stats["skipped"],
            output_path,
            output_snapshot_path,
            chunk_path,
            chunk_snapshot_path,
        )
        self._print_summary(stats, all_docs, len(chunks))
        return all_docs

    def run_directory(self, input_dir: str | Path, extensions: list[str] | None = None) -> list[CleanDocument]:
        input_dir = Path(input_dir)
        allowed = set(extensions or supported_extensions())
        paths: list[Path] = []
        def _walk_error(exc: OSError) -> None:
            logger.warning("Error while walking '%s': %s", input_dir, exc)

        for root, _, files in os.walk(input_dir, onerror=_walk_error):
            root_path = Path(root)
            for file_name in files:
                path = root_path / file_name
                if path.suffix.lstrip(".").lower() in allowed:
                    paths.append(path)
        paths.sort(key=lambda p: str(p.resolve()).lower())
        if not paths:
            logger.warning("No supported files found in '%s'.", input_dir)
            return []
        logger.info("Found %d file(s) to process in '%s'.", len(paths), input_dir)
        return self.run(paths)

    @staticmethod
    def _print_summary(stats: dict, docs: list[CleanDocument], chunk_count: int) -> None:
        lang_counts: dict[str, int] = {}
        arabic_count = 0
        for d in docs:
            lang_counts[d.detected_lang] = lang_counts.get(d.detected_lang, 0) + 1
            if d.is_arabic:
                arabic_count += 1

        print("\n" + "=" * 60)
        print("  PREPROCESSING SUMMARY")
        print("=" * 60)
        print(f"  Files processed   : {stats['files']}")
        print(f"  Raw pages/sections: {stats['raw_pages']}")
        print(f"  Clean documents   : {stats['clean_docs']}")
        print(f"  Chunks generated  : {chunk_count}")
        print(f"  Skipped / empty   : {stats['skipped']}")
        print(f"  Arabic documents  : {arabic_count}")
        print(f"  Language breakdown: {lang_counts}")
        print("=" * 60 + "\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m preprocessing.pipeline",
        description="RAG Phase 1 — Preprocessing + Chunking Pipeline",
    )
    p.add_argument("--input-dir", default="data/raw", help="Directory with raw documents (default: data/raw).")
    p.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory to write outputs (default: data/processed).",
    )
    p.add_argument(
        "--extensions",
        default=",".join(supported_extensions()),
        help="Comma-separated file extensions to process.",
    )
    p.add_argument("--min-words", type=int, default=5)
    p.add_argument(
        "--project-id",
        help="Required when indexing to the vector DB so each corpus stays isolated.",
    )
    p.add_argument(
        "--chunk-strategy",
        default="sentence_window",
        choices=["paragraph", "sentence_window"],
        help="Chunking strategy to export for Member 2 handoff.",
    )
    p.add_argument("--keep-diacritics", action="store_true")
    p.add_argument(
        "--index-to-vectordb",
        action="store_true",
        help="Also embed and push generated chunks to the configured vector database.",
    )
    p.add_argument(
        "--reset-vectordb",
        action="store_true",
        help="Delete the target collection before indexing. Use with care.",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip already indexed chunks when the stored payload still matches the current chunk.",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p


def main() -> None:
    args = _build_arg_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    pipeline = PreprocessingPipeline(
        output_dir=args.output_dir,
        project_id=args.project_id,
        min_words=args.min_words,
        chunk_strategy=args.chunk_strategy,
        index_to_vectordb=args.index_to_vectordb,
        reset_vectordb=args.reset_vectordb,
        skip_existing=args.skip_existing,
        remove_arabic_diacritics=not args.keep_diacritics,
    )
    pipeline.run_directory(
        input_dir=args.input_dir,
        extensions=args.extensions.split(","),
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
