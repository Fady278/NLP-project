"""
Document model — the canonical unit flowing through the RAG pipeline.

Every loader produces a list of RawDocument objects; the cleaning step
transforms them into CleanDocument objects; chunking (Phase 2) will
then split CleanDocuments into Chunk objects stored in the vector DB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    """
    Output of a Loader: raw, un-cleaned text plus rich metadata.

    Attributes
    ----------
    doc_id       : Deterministic SHA-256 hash of (file_hash + page_num).
    content_hash : SHA-256 hash of raw_text for duplicate/content comparison.
    source_path  : Absolute path to the original file (stored in metadata for tracking).
    file_type    : Extension without the dot, lower-cased  (e.g. "pdf").
    page_num     : Page / section index (0-based). -1 when not applicable.
    raw_text     : Verbatim text as extracted from the source.
    metadata     : Arbitrary key-value pairs (author, title, language …).
    extracted_at : ISO-8601 timestamp of extraction.
    """

    source_path: str
    file_type: str
    page_num: int
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    file_hash: str = ""
    content_hash: str = field(init=False)
    doc_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.content_hash = hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()
        if not self.file_hash:
            self.file_hash = self.content_hash
            logger.warning(
                "RawDocument for '%s' was created without file_hash; "
                "falling back to content-derived identity.",
                self.source_path,
            )
            self.metadata["identity_fallback"] = "content_hash"
        seed = f"{self.file_hash}::{self.page_num}"
        self.doc_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        self.metadata["source_path"] = self.source_path
        self.metadata["extracted_at"] = self.extracted_at
        self.metadata["raw_content_hash"] = self.content_hash

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CleanDocument:
    """
    Output of the Cleaner: a RawDocument whose text has been normalised.

    Attributes
    ----------
    doc_id          : Inherited from the source RawDocument.
    source_path     : Inherited.
    file_type       : Inherited.
    page_num        : Inherited.
    clean_text      : Normalised, de-noised text ready for chunking.
    char_count      : Character count of clean_text (post-cleaning).
    word_count      : Whitespace-delimited word count.
    detected_lang   : ISO 639-1 language code detected heuristically.
    is_arabic       : True when Arabic script is dominant (> 30 % chars).
    metadata        : Merged metadata from source + cleaning step.
    """

    doc_id: str
    source_path: str
    file_type: str
    page_num: int
    clean_text: str
    char_count: int
    word_count: int
    detected_lang: str
    is_arabic: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(
        cls,
        raw: RawDocument,
        clean_text: str,
        detected_lang: str,
        is_arabic: bool,
        extra_metadata: dict | None = None,
    ) -> "CleanDocument":
        meta = {**raw.metadata, **(extra_metadata or {})}
        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        meta["content_hash"] = content_hash
        meta["raw_content_hash"] = raw.content_hash
        meta["file_hash"] = raw.file_hash
        return cls(
            doc_id=raw.doc_id,
            source_path=raw.source_path,
            file_type=raw.file_type,
            page_num=raw.page_num,
            clean_text=clean_text,
            char_count=len(clean_text),
            word_count=len(clean_text.split()),
            detected_lang=detected_lang,
            is_arabic=is_arabic,
            metadata=meta,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def is_empty(self, min_words: int = 5) -> bool:
        """Return True when the document carries too little content to be useful."""
        return self.word_count < min_words


def save_documents(docs: list[CleanDocument], output_path: str | Path) -> None:
    """Persist a list of CleanDocuments to a JSON-lines file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=output_path.parent,
        suffix=output_path.suffix or ".jsonl",
    ) as fh:
        for doc in docs:
            fh.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
        temp_path = Path(fh.name)
    os.replace(temp_path, output_path)


def load_documents(input_path: str | Path) -> list[CleanDocument]:
    """Load CleanDocuments previously saved with save_documents()."""
    input_path = Path(input_path)
    docs = []
    with input_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            data = json.loads(line)
            docs.append(CleanDocument(**data))
    return docs
