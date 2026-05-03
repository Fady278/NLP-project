from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from api.schemas.ingest import IngestResponse
from api.services.errors import PipelineExecutionError
from api.services.system_service import SystemDataService
from preprocessing.pipeline import PreprocessingPipeline


class IngestionApplicationService:
    def __init__(self, system_data_service: SystemDataService | None = None) -> None:
        self.system_data_service = system_data_service or SystemDataService()

    def execute(
        self,
        *,
        input_dir: str | Path,
        project_id: str | None = None,
        output_dir: str = "data/processed",
        extensions: list[str] | None = None,
        min_words: int = 5,
        chunk_strategy: str = "sentence_window",
        keep_diacritics: bool = False,
        index_to_vectordb: bool = False,
        reset_vectordb: bool = False,
        skip_existing: bool = True,
    ) -> IngestResponse:
        input_path = Path(input_dir)

        pipeline = PreprocessingPipeline(
            output_dir=output_dir,
            project_id=project_id,
            min_words=min_words,
            chunk_strategy=chunk_strategy,
            index_to_vectordb=index_to_vectordb,
            reset_vectordb=reset_vectordb,
            skip_existing=skip_existing,
            remove_arabic_diacritics=not keep_diacritics,
        )

        try:
            if input_path.is_dir():
                docs = pipeline.run_directory(
                    input_dir=input_path,
                    extensions=extensions,
                )
            elif input_path.is_file():
                docs = pipeline.run([input_path])
            else:
                raise PipelineExecutionError(
                    "Input path does not exist",
                    str(input_path),
                )
        except Exception as exc:  # noqa: BLE001
            raise PipelineExecutionError(
                "Ingestion pipeline failed",
                str(exc),
            ) from exc

        chunk_file = Path(output_dir) / f"chunks_{chunk_strategy}__{pipeline.ingestion_id}.jsonl"
        chunks_created = self._count_jsonl_lines(chunk_file)
        source_paths = sorted({
            str(doc.source_path)
            for doc in docs
            if getattr(doc, "source_path", None)
        })
        file_hashes = sorted({
            str(doc.metadata.get("file_hash"))
            for doc in docs
            if isinstance(doc.metadata.get("file_hash"), str) and doc.metadata.get("file_hash")
        })

        file_name = input_path.name if input_path.name else str(input_path)
        self.system_data_service.record_ingestion_activity(
            file_name=file_name,
            chunks_created=chunks_created,
            project_id=project_id,
        )
        self.system_data_service.save_ingestion_job(
            {
                "id": f"ingest-{uuid.uuid4().hex[:12]}",
                "file_name": file_name,
                "file_size": self._safe_size(input_path),
                "file_type": "directory" if input_path.is_dir() else input_path.suffix.lstrip(".").lower() or "unknown",
                "status": "indexed",
                "progress": 100,
                "chunks_created": chunks_created,
                "error_message": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "project_id": project_id,
                    "input_path": str(input_path),
                    "output_dir": str(Path(output_dir)),
                    "chunk_strategy": chunk_strategy,
                    "documents_processed": len(docs),
                    "ingestion_id": pipeline.ingestion_id,
                    "source_paths": source_paths,
                    "file_hashes": file_hashes,
                    "skip_existing": skip_existing,
                },
            }
        )

        return IngestResponse(
            message="Ingestion completed",
            documents_processed=len(docs),
            output_dir=str(Path(output_dir)),
            metadata={
                "project_id": project_id,
                "chunk_strategy": chunk_strategy,
                "index_to_vectordb": index_to_vectordb,
                "ingestion_id": pipeline.ingestion_id,
                "chunks_created": chunks_created,
            },
        )

    @staticmethod
    def _count_jsonl_lines(path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())

    @staticmethod
    def _safe_size(path: Path) -> int:
        try:
            if path.is_file():
                return path.stat().st_size
        except OSError:
            return 0
        return 0
