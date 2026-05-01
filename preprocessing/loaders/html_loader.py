"""
HTML Loader
-----------
Extracts clean text from HTML files or raw HTML strings using
BeautifulSoup + lxml.

Design decisions
~~~~~~~~~~~~~~~~
* Strips script, style, nav, footer, and ad-related tags before text
  extraction — these produce noise with zero semantic value.
* Splits on <article>, <section>, or <h1>/<h2> boundaries to produce
  logical page-level chunks (consistent with PDF/DOCX page semantics).
* Detects encoding from the HTTP charset meta tag, falling back to
  chardet byte-level detection, so the loader handles legacy documents
  and Arabic / multilingual HTML correctly.
* Can load from file path or accept a raw HTML string directly via the
  class method `from_string()`.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from lxml import html as lxml_html

try:
    from bs4 import BeautifulSoup, Comment, Tag
except ImportError:  # pragma: no cover
    BeautifulSoup = None
    Comment = None
    Tag = object

try:
    import chardet
except ImportError:  # pragma: no cover
    chardet = None

from preprocessing.loaders.base_loader import BaseLoader
from preprocessing.models.document import RawDocument

logger = logging.getLogger(__name__)

# Tags whose entire sub-tree is noise — remove before extraction.
_NOISE_TAGS = {
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "button", "iframe", "svg", "canvas",
    "figure",  # captions sometimes ok, but usually noise in raw HTML
}

# Block-level section boundaries — we split the document here.
_SECTION_TAGS = {"article", "section", "main"}
_HEADING_TAGS = {"h1", "h2"}
_CONTENT_TAGS = {"p", "li", "td", "th"}


class HTMLLoader(BaseLoader):
    SUPPORTED_EXTENSIONS = ("html", "htm")

    def __init__(self, path: str | Path) -> None:
        super().__init__(path)
        self._raw_bytes: bytes | None = None  # set by from_string fallback

    # ------------------------------------------------------------------
    # Alternative constructor — load from string rather than file
    # ------------------------------------------------------------------
    @classmethod
    def from_string(cls, html: str, virtual_path: str = "inline.html") -> "HTMLLoader":
        obj = cls.__new__(cls)
        obj.path = Path(virtual_path)
        obj._raw_bytes = html.encode("utf-8")
        obj._file_hash = hashlib.sha256(obj._raw_bytes).hexdigest()
        return obj

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> list[RawDocument]:
        html_bytes = self._raw_bytes or self.path.read_bytes()
        encoding = self._detect_encoding(html_bytes)
        html_str = html_bytes.decode(encoding, errors="replace")

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html_str, "lxml")
            self._strip_noise(soup)
            meta = self._extract_html_metadata(soup)
            sections = self._extract_sections(soup)
        else:
            meta = self._extract_html_metadata_fallback(html_str)
            sections = self._extract_sections_fallback(html_str)
        meta["html_encoding"] = encoding
        docs: list[RawDocument] = []

        for idx, (title, text) in enumerate(sections):
            section_meta = {**meta, "section_title": title}
            docs.append(
                self._make_doc(text, page_num=idx, extra_meta=section_meta)
            )

        logger.info(
            "HTMLLoader: loaded %d section(s) from '%s'.", len(docs), self.path.name
        )
        return docs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_encoding(raw: bytes) -> str:
        """Charset priority: HTTP-equiv meta → chardet heuristic → utf-8."""
        # Try meta charset first (fast)
        snippet = raw[:4096].decode("latin-1", errors="replace")
        match = re.search(r'charset=["\']?([\w-]+)', snippet, re.I)
        if match:
            return match.group(1).lower()
        # Byte-level heuristic
        if chardet is not None:
            detected = chardet.detect(raw)
            return detected.get("encoding") or "utf-8"
        return "utf-8"

    @staticmethod
    def _strip_noise(soup: BeautifulSoup) -> None:
        """Remove comments and known-noisy tags in place."""
        if Comment is None:
            return
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()
        for tag_name in _NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

    def _extract_sections(
        self, soup: BeautifulSoup
    ) -> list[tuple[str, str]]:
        """
        Return list of (section_title, plain_text) pairs.
        Splits on <article>/<section>/<main> or <h1>/<h2> if none found.
        """
        # Try semantic section tags first
        section_roots = soup.find_all(_SECTION_TAGS)
        if section_roots:
            results = []
            for root in section_roots:
                title = self._section_title(root)
                text = self._tag_to_text(root)
                if text.strip():
                    results.append((title, text))
            if results:
                return results

        # Fall back: split at heading boundaries
        return self._split_by_headings(soup)

    @staticmethod
    def _split_by_headings(soup: BeautifulSoup) -> list[tuple[str, str]]:
        sections: list[tuple[str, list[str]]] = []
        current_title = ""
        current_parts: list[str] = []

        body = soup.find("body") or soup
        for tag in body.find_all(list(_HEADING_TAGS | _CONTENT_TAGS)):
            if tag.name in _HEADING_TAGS:
                heading_text = tag.get_text(" ", strip=True)
                if heading_text:
                    if current_parts or current_title:
                        sections.append((current_title, current_parts))
                    current_title = heading_text
                    current_parts = []
            else:
                if any(p.name in _CONTENT_TAGS for p in tag.parents):
                    continue
                text = tag.get_text(" ", strip=True)
                if text:
                    current_parts.append(text)

        if current_parts:
            sections.append((current_title, current_parts))

        if not sections:
            # Last resort: whole document as one section
            body = soup.find("body") or soup
            return [("", body.get_text("\n", strip=True))]

        return [(title, "\n".join(parts)) for title, parts in sections]

    @staticmethod
    def _section_title(tag: Tag) -> str:
        heading = tag.find(_HEADING_TAGS)
        if heading:
            return heading.get_text(" ", strip=True)
        return tag.get("id") or tag.get("class", [""])[0] or ""

    @staticmethod
    def _tag_to_text(tag: Tag) -> str:
        return tag.get_text("\n", strip=True)

    @staticmethod
    def _extract_html_metadata(soup: BeautifulSoup) -> dict:
        meta: dict = {}
        title_tag = soup.find("title")
        meta["html_title"] = title_tag.get_text(strip=True) if title_tag else ""
        for m in soup.find_all("meta"):
            name = m.get("name", m.get("property", "")).lower()
            content = m.get("content", "")
            if name in ("author", "description", "keywords", "og:title", "og:description"):
                meta[f"meta_{name.replace(':', '_')}"] = content
        return meta

    @staticmethod
    def _extract_html_metadata_fallback(html_str: str) -> dict:
        meta: dict = {}
        try:
            tree = lxml_html.fromstring(html_str)
            titles = tree.xpath("//title/text()")
            meta["html_title"] = titles[0].strip() if titles else ""
        except Exception:
            meta["html_title"] = ""
        return meta

    @staticmethod
    def _extract_sections_fallback(html_str: str) -> list[tuple[str, str]]:
        try:
            tree = lxml_html.fromstring(html_str)
            texts = []
            for node in tree.xpath("//body//*[self::h1 or self::h2 or self::p or self::li]"):
                text = " ".join(t.strip() for t in node.itertext() if t.strip())
                if text:
                    texts.append(text)
            if texts:
                return [("", "\n".join(texts))]
            body_text = " ".join(t.strip() for t in tree.xpath("//body//text()") if t.strip())
            return [("", body_text)] if body_text else []
        except Exception:
            return [("", html_str.strip())] if html_str.strip() else []
