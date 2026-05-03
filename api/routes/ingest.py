from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile

from api.schemas.ingest import DeleteIngestionResponse, IngestRequest, IngestResponse
from api.services.deletion_service import IngestionDeletionService
from api.services.errors import PipelineExecutionError
from api.services.ingestion_service import IngestionApplicationService

router = APIRouter(tags=["ingest"])


def get_ingestion_service() -> IngestionApplicationService:
    return IngestionApplicationService()


def get_deletion_service() -> IngestionDeletionService:
    return IngestionDeletionService()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(
    request: Request,
    service: IngestionApplicationService = Depends(get_ingestion_service),
) -> IngestResponse:
    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not _is_uploaded_file(upload):
            raise PipelineExecutionError("Multipart ingestion requires a 'file' field.")

        project_id = _optional_form_value(form.get("project_id"))
        output_dir = _optional_form_value(form.get("output_dir")) or "data/processed"
        chunk_strategy = _optional_form_value(form.get("chunk_strategy")) or "sentence_window"
        keep_diacritics = _bool_form_value(form.get("keep_diacritics"), default=False)
        index_to_vectordb = _bool_form_value(form.get("index_to_vectordb"), default=True)
        reset_vectordb = _bool_form_value(form.get("reset_vectordb"), default=False)
        skip_existing = _bool_form_value(form.get("skip_existing"), default=False)

        upload_path = _save_upload(upload)
        try:
            return service.execute(
                input_dir=upload_path,
                project_id=project_id,
                output_dir=output_dir,
                min_words=5,
                chunk_strategy=chunk_strategy,
                keep_diacritics=keep_diacritics,
                index_to_vectordb=index_to_vectordb,
                reset_vectordb=reset_vectordb,
                skip_existing=skip_existing,
            )
        finally:
            await upload.close()

    payload = IngestRequest.model_validate(await request.json())
    return service.execute(
        input_dir=payload.input_dir,
        project_id=payload.project_id,
        output_dir=payload.output_dir,
        extensions=payload.extensions,
        min_words=payload.min_words,
        chunk_strategy=payload.chunk_strategy,
        keep_diacritics=payload.keep_diacritics,
        index_to_vectordb=payload.index_to_vectordb,
        reset_vectordb=payload.reset_vectordb,
        skip_existing=payload.skip_existing,
    )


@router.delete("/ingest/jobs/{job_id}", response_model=DeleteIngestionResponse)
def delete_ingestion_job_endpoint(
    job_id: str,
    service: IngestionDeletionService = Depends(get_deletion_service),
) -> DeleteIngestionResponse:
    return service.delete_job(job_id)


def _save_upload(upload: UploadFile) -> Path:
    upload_dir = Path("data/raw/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.filename or f"upload-{uuid.uuid4().hex}").name
    target = upload_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    with target.open("wb") as fh:
        shutil.copyfileobj(upload.file, fh)
    return target


def _is_uploaded_file(value: object) -> bool:
    return bool(
        value is not None
        and hasattr(value, "filename")
        and hasattr(value, "file")
    )


def _optional_form_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bool_form_value(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
