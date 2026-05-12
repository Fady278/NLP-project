from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from preprocessing.loaders.base_loader import BaseLoader
from preprocessing.models.document import RawDocument

logger = logging.getLogger(__name__)

# A page with fewer raw characters than this is likely a scan / image page.
_SCANNED_PAGE_CHAR_THRESHOLD = 50


class PDFLoader(BaseLoader):
    SUPPORTED_EXTENSIONS = ("pdf",)

    def __init__(self, path: str | Path, *, warn_on_scanned: bool = True) -> None:
        super().__init__(path)
        self.warn_on_scanned = warn_on_scanned

  
    def load(self) -> list[RawDocument]:
        try:
            reader = PdfReader(str(self.path))
        except PdfReadError as exc:
            logger.error("Cannot open PDF '%s': %s", self.path.name, exc)
            raise IOError(f"Cannot open PDF '{self.path.name}': {exc}")

        pdf_meta = self._extract_pdf_metadata(reader)
        docs: list[RawDocument] = []

        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Page %d of '%s' could not be parsed: %s — skipping.",
                    page_num,
                    self.path.name,
                    exc,
                )
                continue

            if len(text.strip()) < _SCANNED_PAGE_CHAR_THRESHOLD:
                if self.warn_on_scanned:
                    logger.warning(
                        "Page %d of '%s' yielded very little text (%d chars). "
                        "This page may be scanned — consider adding OCR.",
                        page_num,
                        self.path.name,
                        len(text.strip()),
                    )

            page_meta = {
                **pdf_meta,
                "total_pages": len(reader.pages),
                "page_label": self._safe_page_label(reader, page_num),
            }
            docs.append(self._make_doc(text, page_num=page_num, extra_meta=page_meta))

        logger.info(
            "PDFLoader: loaded %d page(s) from '%s'.", len(docs), self.path.name
        )
        return docs

  
@staticmethod
    def _extract_pdf_metadata(reader: PdfReader) -> dict:
        info = reader.metadata or {}
        return {
            "pdf_title": info.get("/Title", ""),
            "pdf_author": info.get("/Author", ""),
            "pdf_subject": info.get("/Subject", ""),
            "pdf_creator": info.get("/Creator", ""),
            "pdf_created": str(info.get("/CreationDate", "")),
            "pdf_modified": str(info.get("/ModDate", "")),
        }

    @staticmethod
    def _safe_page_label(reader: PdfReader, page_num: int) -> str:
        try:
            return reader.page_labels[page_num]
        except Exception:  
            return str(page_num + 1)
