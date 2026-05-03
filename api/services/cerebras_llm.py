from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from api.services.errors import DependencyConfigurationError, ProviderError


class CerebrasLLMService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("CEREBRAS_API_KEY")
        self.base_url = (base_url or os.getenv("CEREBRAS_API_BASE_URL") or "https://api.cerebras.ai/v1").rstrip("/")
        self.model = model or os.getenv("CEREBRAS_MODEL") or "qwen-3-235b-a22b-instruct-2507"
        self.timeout_seconds = float(timeout_seconds or os.getenv("CEREBRAS_TIMEOUT_SECONDS") or "30")

        if not self.api_key:
            raise DependencyConfigurationError(
                "Cerebras API key is not configured",
                "Set CEREBRAS_API_KEY in the server environment.",
            )

    @property
    def provider_name(self) -> str:
        return "cerebras"

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        response_data = self._post_json("/chat/completions", payload)
        return self._extract_text(response_data)

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
        }

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
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
                "Cerebras request failed",
                details or f"HTTP {exc.code} returned by Cerebras.",
            ) from exc
        except error.URLError as exc:
            raise ProviderError(
                "Cerebras request failed",
                str(exc.reason),
            ) from exc
        except TimeoutError as exc:
            raise ProviderError(
                "Cerebras request timed out",
                f"Timed out after {self.timeout_seconds} second(s).",
            ) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "Cerebras returned an invalid response",
                "Response body was not valid JSON.",
            ) from exc

        if not isinstance(parsed, dict):
            raise ProviderError(
                "Cerebras returned an invalid response",
                "Top-level response payload was not a JSON object.",
            )
        return parsed

    @staticmethod
    def _read_error_body(exc: error.HTTPError) -> str | None:
        try:
            raw = exc.read().decode("utf-8").strip()
        except Exception:
            return None
        if not raw:
            return None
        return raw

    @staticmethod
    def _extract_text(response_data: dict[str, Any]) -> str:
        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(
                "Cerebras returned an invalid response",
                "Missing choices in provider response.",
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ProviderError(
                "Cerebras returned an invalid response",
                "First choice was not a JSON object.",
            )

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ProviderError(
                "Cerebras returned an invalid response",
                "Missing message object in provider response.",
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(
                "Cerebras returned an invalid response",
                "Provider response did not include non-empty assistant content.",
            )
        return content.strip()
