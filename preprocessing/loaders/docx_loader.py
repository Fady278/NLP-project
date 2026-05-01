"""
DOCX Loader
-----------
Extracts text from Word (.docx) files using python-docx.

Design decisions
~~~~~~~~~~~~~~~~
* Treats every top-level section (identified by Heading 1/2 style) as a
  logical "page", giving natural segment boundaries without arbitrary
  character splitting.  Falls back to treating the whole document as a
  single unit when no headings are found.
* Preserves table cell text — concatenated row-by-row with pipe
  separators so table structure survives cleaning.
* Core document properties (author, title, last modified) are captured
  into metadata.
"""

from __future__ import annotations

import logging
from pathlib import Path

import docx
from docx import Document

from preprocessing.loaders.base_loader import BaseLoader
from preprocessing.models.document import RawDocument

logger = logging.getLogger(__name__)

_HEADING_STYLES = {"Heading 1", "Heading 2", "heading 1", "heading 2"}
_MIN_SECTION_WORDS = 12


class DOCXLoader(BaseLoader):
    SUPPORTED_EXTENSIONS = ("docx",)

    def load(self) -> list[RawDocument]:
        try:
            doc: Document = docx.Document(str(self.path))
        except Exception as exc:  # noqa: BLE001
            logger.error("Cannot open DOCX '%s': %s", self.path.name, exc)
            raise IOError(f"Cannot open DOCX '{self.path.name}': {exc}")

        core_meta = self._extract_core_properties(doc)
        sections = self._split_into_sections(doc)
        sections = self._merge_short_sections(sections, min_words=_MIN_SECTION_WORDS)
        docs: list[RawDocument] = []

        for idx, (heading, paragraphs) in enumerate(sections):
            text = self._section_to_text(heading, paragraphs)
            meta = {
                **core_meta,
                "section_heading": heading or "",
                "total_sections": len(sections),
            }
            docs.append(self._make_doc(text, page_num=idx, extra_meta=meta))

        logger.info(
            "DOCXLoader: loaded %d section(s) from '%s'.", len(docs), self.path.name
        )
        return docs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _split_into_sections(
        self, doc: Document
    ) -> list[tuple[str, list]]:
        """
        Group paragraphs by Heading 1 / Heading 2 boundaries.
        Returns a list of (heading_text, [paragraph, ...]) tuples.
        """
        sections: list[tuple[str, list]] = []
        current_heading = ""
        current_paras: list = []

        for block in self._iter_blocks(doc):
            if isinstance(block, docx.text.paragraph.Paragraph):
                if block.style.name in _HEADING_STYLES and block.text.strip():
                    if current_paras or current_heading:
                        sections.append((current_heading, current_paras))
                    current_heading = block.text.strip()
                    current_paras = []
                else:
                    current_paras.append(block)
            else:
                # It's a table
                current_paras.append(block)

        if current_paras or current_heading:
            sections.append((current_heading, current_paras))

        # If no headings were found, the whole doc is one section
        if not sections:
            all_blocks = list(self._iter_blocks(doc))
            sections = [("", all_blocks)]

        return sections

    @staticmethod
    def _merge_short_sections(
        sections: list[tuple[str, list]],
        min_words: int = 12,
    ) -> list[tuple[str, list]]:
        """
        Merge tiny heading-only sections with the next or previous section.
        This reduces low-context fragments such as title-only blocks.
        """
        if not sections:
            return sections

        merged: list[tuple[str, list]] = []
        i = 0
        while i < len(sections):
            heading, blocks = sections[i]
            text = DOCXLoader._section_to_text(heading, blocks)
            word_count = len(text.split())

            if word_count >= min_words or len(sections) == 1:
                merged.append((heading, blocks))
                i += 1
                continue

            if i + 1 < len(sections):
                next_heading, next_blocks = sections[i + 1]
                combined_heading = heading or next_heading
                combined_blocks = blocks + next_blocks
                sections[i + 1] = (combined_heading, combined_blocks)
                i += 1
                continue

            if merged:
                prev_heading, prev_blocks = merged.pop()
                merged.append((prev_heading or heading, prev_blocks + blocks))
            else:
                merged.append((heading, blocks))
            i += 1

        return merged

    @staticmethod
    def _iter_blocks(doc: Document):
        """Yield paragraphs and tables in document order."""
        body = doc.element.body
        for child in body.iterchildren():
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                yield docx.text.paragraph.Paragraph(child, doc)
            elif tag == "tbl":
                yield docx.table.Table(child, doc)

    @staticmethod
    def _section_to_text(heading: str, blocks: list) -> str:
        parts: list[str] = []
        if heading:
            parts.append(heading)
        for block in blocks:
            if isinstance(block, docx.text.paragraph.Paragraph):
                text = block.text.strip()
                if text:
                    parts.append(text)
            elif isinstance(block, docx.table.Table):
                for row in block.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells)
                    if row_text.strip(" |"):
                        parts.append(row_text)
        return "\n".join(parts)

    @staticmethod
    def _extract_core_properties(doc: Document) -> dict:
        try:
            cp = doc.core_properties
            return {
                "docx_title": cp.title or "",
                "docx_author": cp.author or "",
                "docx_created": str(cp.created or ""),
                "docx_modified": str(cp.modified or ""),
                "docx_subject": cp.subject or "",
            }
        except Exception:  # noqa: BLE001
            return {}
