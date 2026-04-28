"""
Text Cleaner
------------
Transforms a RawDocument into a CleanDocument by applying a deterministic
sequence of normalisation steps.

Pipeline (applied in order)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1.  Encoding repair          — fix mojibake / bad byte sequences
2.  Unicode normalisation    — NFC form, collapse variant characters
3.  Arabic-aware processing  — RTL marker removal, Arabic normalisation
4.  Whitespace normalisation — collapse runs of spaces/tabs/newlines
5.  Control-character removal — strip non-printable bytes
6.  Ligature expansion       — expand typographic ligatures (ﬁ → fi)
7.  Hyphen de-wrap           — rejoin words split across PDF line breaks
8.  Language detection       — heuristic: Arabic-script character ratio

Nothing here is lossy at the semantic level — we never remove words,
sentences, or punctuation that could affect meaning.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from preprocessing.models.document import CleanDocument, RawDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Arabic / RTL Unicode ranges we care about
# ---------------------------------------------------------------------------
_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_RTL_MARKERS_RE = re.compile(r"[\u200F\u200E\u202A-\u202E\u2066-\u2069]")

# PDF artefacts: a hyphen at end of line is a soft-hyphen from line-wrapping.
_PDF_HYPHEN_WRAP_RE = re.compile(r"-\n(\w)")

# Multiple blank lines → single blank line
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

# Runs of spaces/tabs (but not newlines, which carry semantic weight)
_HSPACE_RE = re.compile(r"[ \t]+")

# Non-printable control characters (except \n, \r, \t)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Common typographic ligatures without a Unicode decomposition
_LIGATURES: dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}
_LIGATURE_TABLE = str.maketrans(_LIGATURES)

# ---------------------------------------------------------------------------
# Arabic normalisation table
# Alef variants  →  bare Alef (ا)
# Teh Marbuta   →  Heh (ه)   — optional; disabled by default
# Yeh variants  →  Yeh (ي)
# ---------------------------------------------------------------------------
_ARABIC_NORM: dict[int, int] = {
    ord("أ"): ord("ا"),  # Alef with Hamza above
    ord("إ"): ord("ا"),  # Alef with Hamza below
    ord("آ"): ord("ا"),  # Alef with Madda
    ord("ٱ"): ord("ا"),  # Alef Wasla
    ord("ى"): ord("ي"),  # Alef Maqsura → Yeh
    ord("ئ"): ord("ي"),  # Yeh with Hamza
    # Remove Tatweel (kashida, used for calligraphic stretching)
    ord("ـ"): None,
}
_ARABIC_NORM_TABLE = str.maketrans(
    {k: (chr(v) if v is not None else "") for k, v in _ARABIC_NORM.items()}
)

# Diacritic (tashkeel) removal pattern — useful for search normalisation
_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]")
_MOJIBAKE_HINT_RE = re.compile(r"(?:Ã.|Â.|â..|ðŸ|ï¿½)")


class TextCleaner:
    """
    Stateless text cleaner.

    Parameters
    ----------
    remove_arabic_diacritics : bool
        Strip tashkeel (short vowel marks). Default True — diacritics
        rarely appear in modern Arabic business/legal documents and add
        noise for dense-retrieval models.
    arabic_lang_threshold : float
        Fraction of characters that must be Arabic-script for a document
        to be classified as Arabic. Default 0.30 (30 %).
    min_words_threshold : int
        Documents with fewer words after cleaning are logged as warnings
        (still returned — filtering is the pipeline's job).
    """

    def __init__(
        self,
        remove_arabic_diacritics: bool = True,
        arabic_lang_threshold: float = 0.30,
        min_words_threshold: int = 10,
    ) -> None:
        self.remove_arabic_diacritics = remove_arabic_diacritics
        self.arabic_lang_threshold = arabic_lang_threshold
        self.min_words_threshold = min_words_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self, raw: RawDocument) -> CleanDocument:
        text = raw.raw_text

        # Step 1 — encoding repair (mojibake heuristic)
        text = self._repair_encoding(text)

        # Step 2 — Unicode NFC normalisation + ligature expansion
        text = unicodedata.normalize("NFC", text)
        text = text.translate(_LIGATURE_TABLE)

        # Step 3 — RTL marker removal (PDF/Word often inject U+200F etc.)
        text = _RTL_MARKERS_RE.sub("", text)

        # Step 4 — Arabic normalisation
        text = text.translate(_ARABIC_NORM_TABLE)
        if self.remove_arabic_diacritics:
            text = _ARABIC_DIACRITICS_RE.sub("", text)

        # Step 5 — PDF hyphen de-wrapping  (must run before space collapse)
        text = _PDF_HYPHEN_WRAP_RE.sub(r"\1", text)

        # Step 6 — Control characters
        text = _CONTROL_RE.sub("", text)

        # Step 7 — Horizontal whitespace collapse (preserve newlines)
        text = _HSPACE_RE.sub(" ", text)

        # Step 8 — Collapse excess blank lines
        text = _MULTI_BLANK_RE.sub("\n\n", text)

        # Step 9 — Strip leading/trailing whitespace
        text = text.strip()

        # --- Language detection ---
        is_arabic, arabic_ratio = self._detect_arabic(text)
        lang = "ar" if is_arabic else self._detect_latin_lang(text)

        if len(text.split()) < self.min_words_threshold:
            logger.warning(
                "Document %s (page %d) has only %d words after cleaning.",
                raw.source_path,
                raw.page_num,
                len(text.split()),
            )

        return CleanDocument.from_raw(
            raw,
            clean_text=text,
            detected_lang=lang,
            is_arabic=is_arabic,
            extra_metadata={"arabic_char_ratio": round(arabic_ratio, 3)},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_arabic(self, text: str) -> tuple[bool, float]:
        """Return (is_arabic, arabic_char_ratio)."""
        if not text:
            return False, 0.0
        arabic_chars = len(_ARABIC_SCRIPT_RE.findall(text))
        # Only count alphabetic + arabic characters (ignore digits, spaces)
        base_len = sum(1 for c in text if c.isalpha() or _ARABIC_SCRIPT_RE.match(c))
        if base_len == 0:
            return False, 0.0
        ratio = arabic_chars / base_len
        return ratio >= self.arabic_lang_threshold, ratio

    @staticmethod
    def _detect_latin_lang(text: str) -> str:
        """
        Lightweight heuristic for Latin-script languages.
        Uses character n-gram fingerprints for a handful of common langs.
        Falls back to 'en' when uncertain — good enough for retrieval.
        """
        if not text or len(text) < 50:
            return "en"

        sample = text[:2000].lower()

        # Count language-discriminating trigrams
        scores: dict[str, int] = {
            "en": sample.count("the") + sample.count("and") + sample.count("ing"),
            "fr": sample.count("les") + sample.count("des") + sample.count("est"),
            "de": sample.count("die") + sample.count("der") + sample.count("und"),
            "es": sample.count("los") + sample.count("las") + sample.count("que"),
        }
        return max(scores, key=lambda k: scores[k])

    @staticmethod
    def _repair_encoding(text: str) -> str:
        """
        Attempt to fix common mojibake patterns produced by PDF extraction
        when the PDF embeds a Windows-1252 font but is decoded as Latin-1.

        The fix is best-effort; it won't recover all damage.
        """
        if not text or not _MOJIBAKE_HINT_RE.search(text):
            return text

        try:
            # If the string was decoded as latin-1 from utf-8 bytes, re-encode
            # and decode to restore the original characters.
            repaired = text.encode("latin-1").decode("utf-8")
            if _MOJIBAKE_HINT_RE.search(repaired):
                return text

            original_alpha = sum(1 for c in text if c.isalpha())
            repaired_alpha = sum(1 for c in repaired if c.isalpha())
            if original_alpha and repaired_alpha < original_alpha * 0.8:
                return text
            return repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text
