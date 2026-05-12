from __future__ import annotations

import re
from pathlib import Path

from preprocessing.models.document import load_documents

_ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u0600-\u06FF]+")
_FILE_REF_RE = re.compile(r"\.(pdf|docx|html|txt|md|csv|xlsx?)\b", re.IGNORECASE)
_ARABIC_NORM_TABLE = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ئ": "ي",
        "ؤ": "و",
        "ة": "ه",
        "ـ": "",
    }
)


class QueryEnhancer:
    def __init__(self, llm_service, processed_dir: str | Path = "data/processed") -> None:
        self.llm_service = llm_service
        self.processed_dir = Path(processed_dir)
        self._rewrite_cache: dict[tuple[str, str, str], str] = {}
        self._dominant_lang_cache: str | None = None

    def variants_for_query(
        self,
        query: str,
        *,
        conversation_context: str | None = None,
        retrieval_results: list[dict] | None = None,
    ) -> list[str]:
        cleaned = query.strip()
        if not cleaned:
            return []

        variants: list[str] = [cleaned]
        contextual = self._build_contextual_variant(cleaned, conversation_context)
        if contextual and contextual not in variants:
            variants.append(contextual)

        normalized = self.normalize_query(cleaned)
        if normalized and normalized not in variants:
            variants.append(normalized)
        if contextual:
            contextual_normalized = self.normalize_query(contextual)
            if contextual_normalized and contextual_normalized not in variants:
                variants.append(contextual_normalized)

        rewrite_seed = contextual or cleaned
        for target_language in self._crosslingual_rewrite_targets(cleaned, retrieval_results or []):
            rewritten = self._rewrite_query(rewrite_seed, target_language=target_language)
            if rewritten and rewritten not in variants:
                variants.append(rewritten)

        return variants

    def normalize_query(self, query: str) -> str:
        text = query.strip()
        if not text:
            return ""

        text = _ARABIC_DIACRITICS_RE.sub("", text)
        text = text.translate(_ARABIC_NORM_TABLE)
        text = _WHITESPACE_RE.sub(" ", text)
        return text.strip()

    def _crosslingual_rewrite_targets(self, query: str, retrieval_results: list[dict]) -> list[str]:
        query_language = self._detect_query_language(query)
        dominant_lang = self._get_dominant_corpus_language()
        top_score = self._top_score(retrieval_results)
        weak_results = top_score is None or top_score < 0.72

        if query_language == "ar":
            if dominant_lang != "ar" or weak_results:
                return ["en"]
            return []

        if dominant_lang == "ar" or weak_results:
            return ["ar"]
        return []

    def _rewrite_query(self, query: str, *, target_language: str) -> str | None:
        cache_key = (self.llm_service.provider_name, target_language, query.strip())
        if cache_key in self._rewrite_cache:
            return self._rewrite_cache[cache_key]

        if target_language == "en":
            prompt = (
                "You rewrite user questions into short English retrieval queries for an English document corpus.\n"
                "Rules:\n"
                "- Return only one concise English query.\n"
                "- Preserve names and likely transliterate Arabic names into common Latin spelling.\n"
                "- Expand colloquial Arabic meaning into standard English search wording.\n"
                "- Do not explain anything.\n\n"
                f"User question:\n{query}"
            )
        elif target_language == "ar":
            prompt = (
                "You rewrite user questions into short Modern Standard Arabic retrieval queries for an Arabic document corpus.\n"
                "Rules:\n"
                "- Return only one concise Arabic query.\n"
                "- Preserve names and convert English technical intent into natural Arabic search wording when appropriate.\n"
                "- Keep key product, course, or department names if they are usually used as-is.\n"
                "- Do not explain anything.\n\n"
                f"User question:\n{query}"
            )
        else:
            return None

        try:
            rewritten = self.llm_service.generate(prompt).strip()
        except Exception:
            return None

        rewritten = rewritten.strip().strip('"').strip("'")
        rewritten = _WHITESPACE_RE.sub(" ", rewritten)
        if not rewritten:
            return None

        self._rewrite_cache[cache_key] = rewritten
        return rewritten

    def _build_contextual_variant(self, query: str, conversation_context: str | None) -> str | None:
        if not conversation_context:
            return None

        last_user_turn = self._extract_last_user_turn(conversation_context)
        if not last_user_turn:
            return None
        if last_user_turn.strip() == query.strip():
            return None

        if not self._is_followup_like(query, last_user_turn):
            return None

        return f"{last_user_turn}\n{query}".strip()

    @staticmethod
    def _extract_last_user_turn(conversation_context: str) -> str | None:
        user_lines = []
        for raw_line in conversation_context.splitlines():
            line = raw_line.strip()
            if line.lower().startswith("user:"):
                user_lines.append(line.split(":", 1)[1].strip())
        return user_lines[-1] if user_lines else None

    @staticmethod
    def _is_followup_like(query: str, previous_user_turn: str) -> bool:
        normalized = query.strip().lower()
        if not normalized:
            return False

        query_tokens = QueryEnhancer._tokenize(normalized)
        previous_tokens = QueryEnhancer._tokenize(previous_user_turn.lower())
        token_count = len(query_tokens)

        # Very short questions are usually follow-ups and benefit from the
        # previous user turn as a retrieval anchor.
        if token_count <= 4:
            return True

        if _FILE_REF_RE.search(normalized):
            return False

        if any(char.isdigit() for char in normalized):
            return False

        novel_tokens = [token for token in query_tokens if token not in previous_tokens]
        informative_novel_tokens = [token for token in novel_tokens if len(token) >= 4]

        # If the current question mostly reuses earlier context and contributes
        # little new lexical information, treat it as a follow-up.
        if len(informative_novel_tokens) <= 1:
            return True

        previous_count = max(1, len(previous_tokens))
        query_to_previous_ratio = token_count / previous_count
        if query_to_previous_ratio <= 0.45 and len(informative_novel_tokens) <= 2:
            return True

        return False

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [match.group(0).casefold() for match in _WORD_RE.finditer(text)]

    def _get_dominant_corpus_language(self) -> str:
        if self._dominant_lang_cache is not None:
            return self._dominant_lang_cache

        docs_path = self.processed_dir / "clean_documents.jsonl"
        if not docs_path.exists():
            self._dominant_lang_cache = "unknown"
            return self._dominant_lang_cache

        try:
            docs = load_documents(docs_path)
        except Exception:
            self._dominant_lang_cache = "unknown"
            return self._dominant_lang_cache

        counts: dict[str, int] = {}
        for doc in docs:
            counts[doc.detected_lang] = counts.get(doc.detected_lang, 0) + 1

        self._dominant_lang_cache = max(counts, key=counts.get) if counts else "unknown"
        return self._dominant_lang_cache

    @staticmethod
    def _detect_query_language(query: str) -> str:
        return "ar" if _ARABIC_CHAR_RE.search(query) else "en"

    @staticmethod
    def _top_score(retrieval_results: list[dict]) -> float | None:
        if not retrieval_results:
            return None
        score = retrieval_results[0].get("score")
        return float(score) if isinstance(score, (int, float)) else None
