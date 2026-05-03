from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.schemas.system import (
    ActivityEventResponse,
    ChunksResponse,
    DocumentResponse,
    IngestionJobResponse,
    StatsResponse,
)
from api.services.errors import ResourceNotFoundError
from api.services.system_service import SystemDataService

router = APIRouter(tags=["system"])


def get_system_service() -> SystemDataService:
    return SystemDataService()


@router.get("/stats", response_model=StatsResponse)
def stats_endpoint(service: SystemDataService = Depends(get_system_service)) -> StatsResponse:
    return service.get_stats()


@router.get("/activity", response_model=list[ActivityEventResponse])
def activity_endpoint(service: SystemDataService = Depends(get_system_service)) -> list[ActivityEventResponse]:
    return service.get_activity()


@router.get("/documents", response_model=list[DocumentResponse])
def documents_endpoint(service: SystemDataService = Depends(get_system_service)) -> list[DocumentResponse]:
    return service.get_documents()


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def document_endpoint(
    document_id: str,
    service: SystemDataService = Depends(get_system_service),
) -> DocumentResponse:
    document = service.get_document(document_id)
    if document is None:
        raise ResourceNotFoundError("Document not found")
    return document


@router.get("/chunks", response_model=ChunksResponse)
def chunks_endpoint(
    source: str | None = Query(default=None),
    types: str | None = Query(default=None),
    minScore: float | None = Query(default=None),
    maxScore: float | None = Query(default=None),
    service: SystemDataService = Depends(get_system_service),
) -> ChunksResponse:
    file_types = [item.strip() for item in types.split(",") if item.strip()] if types else None
    return service.get_chunks(
        source=source,
        file_types=file_types,
        min_score=minScore,
        max_score=maxScore,
    )


@router.get("/ingest/jobs", response_model=list[IngestionJobResponse])
def ingestion_jobs_endpoint(service: SystemDataService = Depends(get_system_service)) -> list[IngestionJobResponse]:
    return service.get_ingestion_jobs()


@router.get("/ingest/jobs/{job_id}", response_model=IngestionJobResponse)
def ingestion_job_endpoint(
    job_id: str,
    service: SystemDataService = Depends(get_system_service),
) -> IngestionJobResponse:
    job = service.get_ingestion_job(job_id)
    if job is None:
        raise ResourceNotFoundError("Ingestion job not found")
    return job
