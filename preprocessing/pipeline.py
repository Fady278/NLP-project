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

logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    def __init__(
        self,
        output_dir: str | Path = "data/processed",
        min_words: int = 5,
        chunk_strategy: str = "sentence_window",
        **cleaner_kwargs,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_words = min_words
        self.chunk_strategy = chunk_strategy
        self.cleaner = TextCleaner(**cleaner_kwargs)

    def run(self, file_paths: list[str | Path]) -> list[CleanDocument]:
        all_docs: list[CleanDocument] = []
        stats = {"files": 0, "raw_pages": 0, "clean_docs": 0, "skipped": 0}

        for path in file_paths:
            path = Path(path)
            try:
                loader = get_loader(path)
            except (ValueError, FileNotFoundError) as exc:
                logger.warning("Skipping '%s': %s", path.name, exc)
                stats["skipped"] += 1
                continue

            raw_docs = loader.load()
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

        output_path = self.output_dir / "clean_documents.jsonl"
        save_documents(all_docs, output_path)
        chunks = chunk_documents(all_docs, strategy=self.chunk_strategy)
        chunk_path = self.output_dir / f"chunks_{self.chunk_strategy}.jsonl"
        save_chunks(chunks, chunk_path)

        logger.info(
            "Pipeline complete — files: %d | raw pages: %d | clean docs: %d | skipped: %d → saved to %s and %s",
            stats["files"],
            stats["raw_pages"],
            stats["clean_docs"],
            stats["skipped"],
            output_path,
            chunk_path,
        )
        self._print_summary(stats, all_docs, len(chunks))
        return all_docs

    def run_directory(self, input_dir: str | Path, extensions: list[str] | None = None) -> list[CleanDocument]:
        input_dir = Path(input_dir)
        allowed = set(extensions or supported_extensions())
        paths: list[Path] = []
        for root, _, files in os.walk(input_dir, onerror=lambda _: None):
            root_path = Path(root)
            for file_name in files:
                path = root_path / file_name
                if path.suffix.lstrip(".").lower() in allowed:
                    paths.append(path)
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
        "--chunk-strategy",
        default="sentence_window",
        choices=["paragraph", "sentence_window"],
        help="Chunking strategy to export for Member 2 handoff.",
    )
    p.add_argument("--keep-diacritics", action="store_true")
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
        min_words=args.min_words,
        chunk_strategy=args.chunk_strategy,
        remove_arabic_diacritics=not args.keep_diacritics,
    )
    pipeline.run_directory(
        input_dir=args.input_dir,
        extensions=args.extensions.split(","),
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
