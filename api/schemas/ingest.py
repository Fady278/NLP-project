from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IngestRequest(BaseModel):
    input_dir: str = Field(min_length=1)
    project_id: str | None = Field(default=None, min_length=1)
    output_dir: str = Field(default="data/processed", min_length=1)
    extensions: list[str] | None = None
    min_words: int = Field(default=5, ge=1, le=1000)
    chunk_strategy: str = Field(default="sentence_window")
    keep_diacritics: bool = False
    index_to_vectordb: bool = False
    reset_vectordb: bool = False
    skip_existing: bool = True

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("input_dir", "output_dir")
    @classmethod
    def validate_required_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path must not be empty")
        return value

    @field_validator("chunk_strategy")
    @classmethod
    def validate_chunk_strategy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"paragraph", "sentence_window"}:
            raise ValueError("chunk_strategy must be 'paragraph' or 'sentence_window'")
        return normalized

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip().lstrip(".").lower() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("extensions must contain at least one extension when provided")
        return cleaned

    @model_validator(mode="after")
    def validate_project_id_requirements(self) -> "IngestRequest":
        if self.index_to_vectordb and not self.project_id:
            raise ValueError("project_id is required when index_to_vectordb is true")
        return self


class IngestResponse(BaseModel):
    message: str
    documents_processed: int
    output_dir: str
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(extra="forbid")


class DeleteIngestionResponse(BaseModel):
    message: str
    deleted: bool
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(extra="forbid")
