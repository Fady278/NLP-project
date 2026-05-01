from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from preprocessing.models.document import CleanDocument


_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_MIN_CHUNK_TOKENS = 80
_LONG_UNIT_SPLIT_PATTERNS = (
    re.compile(r"(?<=[:;])\s+"),
    re.compile(r"\s+\|\s+"),
    re.compile(r"(?<=,)\s+(?=[A-Z\u0621-\u064A])"),
)
_ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_SENTENCE_END_CHARS = ".!?\u061F"


@dataclass
class Chunk:
    chunk_id: str
    source_doc_id: str
    source_path: str
    file_type: str
    page_num: int
    strategy: str
    text: str
    token_count: int
    char_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def approximate_token_count(text: str) -> int:
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return 0

    base_count = len(tokens)
    word_like_count = sum(1 for tok in tokens if any(ch.isalnum() for ch in tok))
    arabic_char_count = len(_ARABIC_CHAR_RE.findall(text))
    alpha_count = sum(1 for ch in text if ch.isalpha())
    arabic_ratio = (arabic_char_count / alpha_count) if alpha_count else 0.0

    if arabic_ratio >= 0.30:
        return max(base_count, int(round(word_like_count * 1.35)))
    return base_count

_CHUNK_VERSION = "v1"

def _make_chunk_id(source_doc_id: str, strategy: str, index: int | str) -> str:
    return hashlib.sha256(f"{source_doc_id}::{_CHUNK_VERSION}::{strategy}::{index}".encode("utf-8")).hexdigest()


def normalized_chunk_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_content_hash(text: str) -> str:
    return hashlib.sha256(normalized_chunk_text(text).encode("utf-8")).hexdigest()


def _split_oversized_unit(text: str, target_tokens: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if approximate_token_count(text) <= target_tokens:
        return [text]

    for pattern in _LONG_UNIT_SPLIT_PATTERNS:
        pieces = [piece.strip() for piece in pattern.split(text) if piece.strip()]
        if len(pieces) <= 1:
            continue

        refined: list[str] = []
        for piece in pieces:
            if approximate_token_count(piece) > target_tokens and piece != text:
                refined.extend(_split_oversized_unit(piece, target_tokens))
            else:
                refined.append(piece)
        if refined and max(approximate_token_count(piece) for piece in refined) < approximate_token_count(text):
            return refined

    words = text.split()
    if len(words) <= 1:
        return [text]

    midpoint = max(1, len(words) // 2)
    left = " ".join(words[:midpoint]).strip()
    right = " ".join(words[midpoint:]).strip()
    results: list[str] = []
    if left:
        results.extend(_split_oversized_unit(left, target_tokens))
    if right:
        results.extend(_split_oversized_unit(right, target_tokens))
    return results


def _prepare_sentence_units(text: str, target_tokens: int) -> list[str]:
    base_units = _split_sentence_units(text)
    if not base_units:
        base_units = [text.strip()] if text.strip() else []

    prepared: list[str] = []
    for unit in base_units:
        prepared.extend(_split_oversized_unit(unit, target_tokens))
    return prepared


def _split_sentence_units(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    units: list[str] = []
    start = 0
    i = 0
    text_len = len(text)

    while i < text_len:
        ch = text[i]

        if ch == "\n":
            j = i
            while j < text_len and text[j] == "\n":
                j += 1
            if j - i >= 1:
                unit = text[start:i].strip()
                if unit:
                    units.append(unit)
                start = j
            i = j
            continue

        if ch in _SENTENCE_END_CHARS and _is_sentence_boundary(text, i):
            end = i + 1
            while end < text_len and text[end] in "\"')]}":
                end += 1
            unit = text[start:end].strip()
            if unit:
                units.append(unit)
            while end < text_len and text[end].isspace():
                end += 1
            start = end
            i = end
            continue

        i += 1

    tail = text[start:].strip()
    if tail:
        units.append(tail)
    return units


def _is_sentence_boundary(text: str, idx: int) -> bool:
    ch = text[idx]
    if ch != ".":
        return True

    prev_char = text[idx - 1] if idx > 0 else ""
    next_idx = idx + 1
    next_char = text[next_idx] if next_idx < len(text) else ""

    # Avoid splitting decimal numbers like 3.14
    if prev_char.isdigit() and next_char.isdigit():
        return False

    probe = idx + 1
    while probe < len(text) and text[probe].isspace():
        probe += 1
    next_non_space = text[probe] if probe < len(text) else ""

    token_start = idx
    while token_start > 0 and not text[token_start - 1].isspace():
        token_start -= 1
    token = text[token_start : idx + 1].strip("\"')]}")
    alpha_chars = [c for c in token if c.isalpha()]

    # Avoid splitting dotted initialisms like U.S. / A.B. / e.g.
    if token.count(".") > 1 and next_non_space.isalpha():
        return False

    # Avoid splitting after short capitalized titles like Dr. / Mr. / Prof.
    if (
        token.count(".") == 1
        and 1 <= len(alpha_chars) <= 4
        and any(c.isupper() for c in alpha_chars)
        and next_non_space.isalpha()
    ):
        return False

    return True


def _make_chunk(clean_doc: CleanDocument, strategy: str, text: str, index: int) -> Chunk:
    digest = _make_chunk_id(clean_doc.doc_id, strategy, index)
    return Chunk(
        chunk_id=digest,
        source_doc_id=clean_doc.doc_id,
        source_path=clean_doc.source_path,
        file_type=clean_doc.file_type,
        page_num=clean_doc.page_num,
        strategy=strategy,
        text=text,
        token_count=approximate_token_count(text),
        char_count=len(text),
        metadata={
            "lang": clean_doc.detected_lang,
            "is_arabic": clean_doc.is_arabic,
            "chunk_index": index,
            "content_hash": clean_doc.metadata.get("content_hash"),
            "chunk_content_hash": chunk_content_hash(text),
            "file_hash": clean_doc.metadata.get("file_hash"),
        },
    )


def chunk_by_paragraph(clean_doc: CleanDocument, target_tokens: int = 260, overlap: int = 1) -> list[Chunk]:
    paragraphs = [p.strip() for p in re.split(r"\n{1,}", clean_doc.clean_text) if p.strip()]
    if not paragraphs:
        paragraphs = [clean_doc.clean_text.strip()] if clean_doc.clean_text.strip() else []

    chunks: list[Chunk] = []
    buffer: list[str] = []

    for paragraph in paragraphs:
        candidate = "\n\n".join(buffer + [paragraph])
        if buffer and approximate_token_count(candidate) > target_tokens:
            text = "\n\n".join(buffer).strip()
            if text:
                chunks.append(_make_chunk(clean_doc, "paragraph", text, len(chunks)))
            buffer = buffer[-overlap:] if overlap else []
        buffer.append(paragraph)

    if buffer:
        text = "\n\n".join(buffer).strip()
        if text:
            chunks.append(_make_chunk(clean_doc, "paragraph", text, len(chunks)))
    if overlap:
        return chunks
    return _merge_tiny_chunks(chunks, min_tokens=_MIN_CHUNK_TOKENS)


def chunk_by_sentence_window(
    clean_doc: CleanDocument, target_tokens: int = 200, overlap_sentences: int = 1
) -> list[Chunk]:
    sentences = _prepare_sentence_units(clean_doc.clean_text, target_tokens)
    if not sentences:
        sentences = [clean_doc.clean_text.strip()] if clean_doc.clean_text.strip() else []

    chunks: list[Chunk] = []
    cursor = 0
    while cursor < len(sentences):
        current: list[str] = []
        current_tokens = 0
        next_cursor = cursor
        while next_cursor < len(sentences):
            sentence = sentences[next_cursor]
            sent_tokens = approximate_token_count(sentence)
            if current and current_tokens + sent_tokens > target_tokens:
                break
            current.append(sentence)
            current_tokens += sent_tokens
            next_cursor += 1

        if not current:
            current = [sentences[cursor]]
            next_cursor = cursor + 1

        text = " ".join(current).strip()
        if text:
            chunks.append(_make_chunk(clean_doc, "sentence_window", text, len(chunks)))
        cursor = max(cursor + 1, next_cursor - overlap_sentences)
        if cursor == next_cursor:
            cursor += 1
    if overlap_sentences:
        return chunks
    return _merge_tiny_chunks(chunks, min_tokens=_MIN_CHUNK_TOKENS)


def chunk_documents(clean_docs: list[CleanDocument], strategy: str = "sentence_window") -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for clean_doc in clean_docs:
        if strategy == "paragraph":
            all_chunks.extend(chunk_by_paragraph(clean_doc))
        elif strategy == "sentence_window":
            all_chunks.extend(chunk_by_sentence_window(clean_doc))
        else:
            raise ValueError("Unknown chunking strategy. Use 'paragraph' or 'sentence_window'.")
    return all_chunks


def _merge_tiny_chunks(chunks: list[Chunk], min_tokens: int = 80) -> list[Chunk]:
    """
    Merge very small chunks with neighbors to reduce low-context fragments.
    Keeps the original strategy and source metadata.
    """
    if not chunks:
        return []

    merged: list[Chunk] = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        if current.token_count >= min_tokens or len(chunks) == 1:
            merged.append(current)
            i += 1
            continue

        # Prefer merging with the next chunk when available.
        if i + 1 < len(chunks):
            neighbor = chunks[i + 1]
            combined_text = f"{current.text}\n{neighbor.text}".strip()
            combined = Chunk(
                chunk_id=_make_chunk_id(current.source_doc_id, current.strategy, f"merge_fwd_{i}"),
                source_doc_id=current.source_doc_id,
                source_path=current.source_path,
                file_type=current.file_type,
                page_num=current.page_num,
                strategy=current.strategy,
                text=combined_text,
                token_count=approximate_token_count(combined_text),
                char_count=len(combined_text),
                metadata={**neighbor.metadata},
            )
            chunks[i + 1] = combined
            i += 1
            continue

        # If this is the final tiny chunk, merge it backward.
        if merged:
            previous = merged.pop()
            combined_text = f"{previous.text}\n{current.text}".strip()
            merged.append(
                Chunk(
                    chunk_id=_make_chunk_id(previous.source_doc_id, previous.strategy, f"merge_back_{i}"),
                    source_doc_id=previous.source_doc_id,
                    source_path=previous.source_path,
                    file_type=previous.file_type,
                    page_num=previous.page_num,
                    strategy=previous.strategy,
                    text=combined_text,
                    token_count=approximate_token_count(combined_text),
                    char_count=len(combined_text),
                    metadata={**previous.metadata},
                )
            )
        else:
            merged.append(current)
        i += 1

    return merged


def save_chunks(chunks: list[Chunk], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=output_path.parent,
        suffix=output_path.suffix or ".jsonl",
    ) as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
        temp_path = Path(fh.name)
    os.replace(temp_path, output_path)
