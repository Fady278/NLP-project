from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=10000)
    conversation_context: str | None = Field(default=None, max_length=6000)
    top_k: int = Field(default=5, ge=1, le=50)
    prompt_version: str = Field(default="strict")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project_id must not be empty")
        return value

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value

    @field_validator("prompt_version")
    @classmethod
    def validate_prompt_version(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"simple", "strict"}:
            raise ValueError("prompt_version must be either 'simple' or 'strict'")
        return normalized

    @field_validator("conversation_context")
    @classmethod
    def validate_conversation_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class QuerySource(BaseModel):
    source_doc_id: str
    source_path: str
    page_num: int | None = None

    model_config = ConfigDict(extra="forbid")


class RetrievedChunk(BaseModel):
    text: str
    metadata: dict[str, Any] = {}
    score: float | None = None

    model_config = ConfigDict(extra="forbid")


class QueryResponse(BaseModel):
    question: str | None = None
    answer: str
    sources: list[QuerySource]
    retrieved_context: list[RetrievedChunk] | None = None
    metadata: dict[str, Any] = {}
    timestamp: str | None = None
    model_used: str | None = None

    model_config = ConfigDict(extra="forbid")
