"""
Preprocessing Pipeline
-----------------------
The entry-point that wires loaders → cleaner → output together.

Usage (programmatic)
~~~~~~~~~~~~~~~~~~~~
    from preprocessing.pipeline import PreprocessingPipeline

    pipeline = PreprocessingPipeline(output_dir="data/processed")
    clean_docs = pipeline.run(["docs/cv.pdf", "docs/contract.docx"])

Usage (CLI)
~~~~~~~~~~~
    python -m preprocessing.pipeline  \\
        --input-dir  data/raw          \\
        --output-dir data/processed    \\
        --extensions pdf,docx,html

The output is a JSONL file: data/processed/clean_documents.jsonl
Each line is one CleanDocument serialised as JSON.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from preprocessing.cleaners.text_cleaner import TextCleaner
from preprocessing.loaders.registry import get_loader, supported_extensions
from preprocessing.models.document import CleanDocument, save_documents

logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    """
    Orchestrates: load → clean → filter → persist.

    Parameters
    ----------
    output_dir : str | Path
        Directory where clean_documents.jsonl will be written.
    min_words : int
        Documents with fewer words after cleaning are discarded.
        Default: 5 (removes headers, footers, blank pages).
    cleaner_kwargs : dict
        Forwarded to TextCleaner.__init__ (e.g. remove_arabic_diacritics).
    """

    def __init__(
        self,
        output_dir: str | Path = "data/processed",
        min_words: int = 5,
        **cleaner_kwargs,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_words = min_words
        self.cleaner = TextCleaner(**cleaner_kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, file_paths: list[str | Path]) -> list[CleanDocument]:
        """
        Process a list of files and return all CleanDocuments.
        Also writes results to <output_dir>/clean_documents.jsonl.
        """
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

        logger.info(
            "Pipeline complete — files: %d | raw pages: %d | "
            "clean docs: %d | skipped: %d → saved to %s",
            stats["files"],
            stats["raw_pages"],
            stats["clean_docs"],
            stats["skipped"],
            output_path,
        )
        self._print_summary(stats, all_docs)
        return all_docs

    def run_directory(
        self, input_dir: str | Path, extensions: list[str] | None = None
    ) -> list[CleanDocument]:
        """
        Recursively process all supported files in a directory.

        Parameters
        ----------
        extensions : list[str] | None
            Restrict to these extensions (e.g. ["pdf", "docx"]).
            Defaults to all supported types.
        """
        input_dir = Path(input_dir)
        allowed = set(extensions or supported_extensions())
        paths = [
            p
            for p in input_dir.rglob("*")
            if p.is_file() and p.suffix.lstrip(".").lower() in allowed
        ]
        if not paths:
            logger.warning("No supported files found in '%s'.", input_dir)
            return []
        logger.info("Found %d file(s) to process in '%s'.", len(paths), input_dir)
        return self.run(paths)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _print_summary(stats: dict, docs: list[CleanDocument]) -> None:
        """Print a concise human-readable summary to stdout."""
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
        print(f"  Skipped / empty   : {stats['skipped']}")
        print(f"  Arabic documents  : {arabic_count}")
        print(f"  Language breakdown: {lang_counts}")
        print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m preprocessing.pipeline",
        description="RAG Phase 1 — Preprocessing Pipeline",
    )
    p.add_argument("--input-dir", required=True, help="Directory with raw documents.")
    p.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory to write clean_documents.jsonl (default: data/processed).",
    )
    p.add_argument(
        "--extensions",
        default=",".join(supported_extensions()),
        help="Comma-separated file extensions to process.",
    )
    p.add_argument(
        "--min-words",
        type=int,
        default=5,
        help="Minimum word count for a document to be kept (default: 5).",
    )
    p.add_argument(
        "--keep-diacritics",
        action="store_true",
        help="Do NOT strip Arabic tashkeel (diacritics).",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    pipeline = PreprocessingPipeline(
        output_dir=args.output_dir,
        min_words=args.min_words,
        remove_arabic_diacritics=not args.keep_diacritics,
    )
    pipeline.run_directory(
        input_dir=args.input_dir,
        extensions=args.extensions.split(","),
    )
    sys.exit(0)
