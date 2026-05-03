from __future__ import annotations

from fastapi import APIRouter

from api.schemas.common import HealthResponse
from api.services.cerebras_llm import CerebrasLLMService
from api.services.errors import DependencyConfigurationError

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    metadata: dict[str, object] = {}
    try:
        llm = CerebrasLLMService()
        llm_provider = llm.provider_name
        llm_model = llm.model
    except DependencyConfigurationError as exc:
        llm_provider = "cerebras"
        llm_model = "qwen-3-235b-a22b-instruct-2507"
        metadata["warning"] = exc.message
        metadata["details"] = exc.details

    return HealthResponse(
        status="ok",
        service="rag-api",
        llm_provider=llm_provider,
        llm_model=llm_model,
        ingestion_supported=True,
        query_supported=True,
        metadata=metadata,
    )
