from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    error: str
    details: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    llm_provider: str
    llm_model: str
    ingestion_supported: bool
    query_supported: bool
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(extra="forbid")
