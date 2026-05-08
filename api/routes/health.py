from __future__ import annotations

from fastapi import APIRouter

from api.schemas.common import HealthResponse
from api.services.errors import DependencyConfigurationError
from api.services.llm_factory import create_llm_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    metadata: dict[str, object] = {}
    try:
        llm = create_llm_service()
        llm_provider = llm.provider_name
        llm_model = llm.model
    except DependencyConfigurationError as exc:
        llm_provider = "unconfigured"
        llm_model = "unconfigured"
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
