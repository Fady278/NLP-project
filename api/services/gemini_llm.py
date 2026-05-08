from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, parse, request

from api.services.errors import DependencyConfigurationError, ProviderError
from api.services.llm_base import BaseLLMService


class GeminiLLMService(BaseLLMService):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        self.base_url = (
            base_url
            or os.getenv("GEMINI_BASE_URL")
            or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        self._model = (model or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash").strip()
        self.timeout_seconds = float(timeout_seconds or os.getenv("GEMINI_TIMEOUT_SECONDS") or "30")

        if not self.api_key:
            raise DependencyConfigurationError(
                "Gemini API key is not configured",
                "Set GEMINI_API_KEY in the server environment.",
            )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str) -> str:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        response_data = self._post_json(
            f"/models/{self.model}:generateContent",
            payload,
        )
        return self._extract_text(response_data)

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
        }

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        query = parse.urlencode({"key": self.api_key})
        req = request.Request(
            url=f"{self.base_url}{path}?{query}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "NLP-RAG-Project/1.0",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = self._read_error_body(exc)
            raise ProviderError(
                "Gemini request failed",
                details or f"HTTP {exc.code} returned by Gemini.",
            ) from exc
        except error.URLError as exc:
            raise ProviderError(
                "Gemini request failed",
                str(exc.reason),
            ) from exc
        except TimeoutError as exc:
            raise ProviderError(
                "Gemini request timed out",
                f"Timed out after {self.timeout_seconds} second(s).",
            ) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "Gemini returned an invalid response",
                "Response body was not valid JSON.",
            ) from exc

        if not isinstance(parsed, dict):
            raise ProviderError(
                "Gemini returned an invalid response",
                "Top-level response payload was not a JSON object.",
            )
        return parsed

    @staticmethod
    def _read_error_body(exc: error.HTTPError) -> str | None:
        try:
            raw = exc.read().decode("utf-8").strip()
        except Exception:
            return None
        return raw or None

    @staticmethod
    def _extract_text(response_data: dict[str, Any]) -> str:
        candidates = response_data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError(
                "Gemini returned an invalid response",
                "Missing candidates in provider response.",
            )

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ProviderError(
                "Gemini returned an invalid response",
                "First candidate was not a JSON object.",
            )

        content = first_candidate.get("content")
        if not isinstance(content, dict):
            raise ProviderError(
                "Gemini returned an invalid response",
                "Missing content object in provider response.",
            )

        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ProviderError(
                "Gemini returned an invalid response",
                "Missing parts in provider response.",
            )

        text_parts = []
        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())

        if not text_parts:
            raise ProviderError(
                "Gemini returned an invalid response",
                "Provider response did not include non-empty assistant content.",
            )
        return "\n".join(text_parts)
