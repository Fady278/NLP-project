from __future__ import annotations

import os

from api.services.cerebras_llm import CerebrasLLMService
from api.services.errors import DependencyConfigurationError
from api.services.gemini_llm import GeminiLLMService
from api.services.llm_base import BaseLLMService


def create_llm_service(provider: str | None = None) -> BaseLLMService:
    normalized = (provider or os.getenv("LLM_PROVIDER") or "cerebras").strip().lower()

    if normalized == "cerebras":
        return CerebrasLLMService()
    if normalized == "gemini":
        return GeminiLLMService()

    raise DependencyConfigurationError(
        "Unsupported LLM provider configured",
        f"LLM_PROVIDER='{normalized}' is not supported. Use cerebras or gemini.",
    )
