import os
import hashlib
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)


class VectorDBClient:
    def __init__(self, host="localhost", port=6333):
        self._load_env_file()

        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        api_key_file = os.getenv("QDRANT_API_KEY_FILE")

        if not api_key:
            key_path = self._resolve_api_key_path(api_key_file or "rag-project_api_key.txt")

            if key_path.exists():
                api_key = key_path.read_text(encoding="utf-8").strip()
            elif api_key_file:
                raise ValueError(f"Qdrant API key file not found: {key_path}")

            if api_key_file and not api_key:
                raise ValueError(f"Qdrant API key file is empty: {key_path}")

        if url and not api_key:
            raise ValueError(
                "QDRANT_URL is configured but no API key was found. "
                "Set QDRANT_API_KEY or QDRANT_API_KEY_FILE."
            )

        if url:
            self.client = QdrantClient(
                url=url,
                api_key=api_key,
                timeout=60,
                check_compatibility=False
            )
        else:
            self.client = QdrantClient(host=host, port=port)

    def _load_env_file(self):
        current_dir = Path(__file__).resolve().parent
        env_path = None
        for _ in range(4):
            candidate = current_dir / ".env"
            if candidate.exists():
                env_path = candidate
                break
            current_dir = current_dir.parent

        if not env_path:
            return

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

    def _resolve_api_key_path(self, api_key_file):
        key_path = Path(api_key_file)
        if not key_path.is_absolute():
            key_path = Path(__file__).resolve().parents[2] / key_path
        return key_path

    def create_collection_name(self, project_id):
        return f"collection_{project_id}".strip()

    def _normalize_point_id(self, point_id):
        if isinstance(point_id, int):
            return point_id

        point_id = str(point_id).strip()
        if point_id.isdigit():
            return int(point_id)

        return int(hashlib.sha256(point_id.encode()).hexdigest()[:16], 16)

    # -------------------------
    # CREATE COLLECTION
    # -------------------------
    def create_collection(self, name, dim):
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]

        if name not in existing:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE
                )
            )

        self._ensure_payload_indexes(name)

    def _ensure_payload_indexes(self, collection_name):
        payload_indexes = (
            "metadata.lang",
            "metadata.file_type",
            "metadata.strategy",
            "metadata.source_doc_id",
        )

        for field_name in payload_indexes:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True
            )

    # -------------------------
    # ADD DOCUMENTS (INDEXING)
    # -------------------------
    def add_documents(self, collection_name, texts, vectors, metadata, point_ids=None):
        if point_ids is None:
            point_ids = [meta.get("chunk_id") or meta.get("doc_id") for meta in metadata]

        batch_size = 128

        for start in range(0, len(texts), batch_size):
            end = start + batch_size
            points = []

            for point_id, text, vector, meta in zip(
                point_ids[start:end],
                texts[start:end],
                vectors[start:end],
                metadata[start:end],
            ):
                points.append(
                    PointStruct(
                        id=self._normalize_point_id(point_id),
                        vector=vector,
                        payload={
                            "text": text,
                            "metadata": meta
                        }
                    )
                )

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.client.upsert(
                        collection_name=collection_name,
                        points=points,
                        wait=True
                    )
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e

    # -------------------------
    # SEARCH (IMPORTANT FOR RAG)
    # -------------------------
    def _build_filter(self, metadata_filter):
        if not metadata_filter:
            return None

        conditions = []
        for key, value in metadata_filter.items():
            conditions.append(
                FieldCondition(
                    key=f"metadata.{key}",
                    match=MatchValue(value=value)
                )
            )

        if not conditions:
            return None

        return Filter(must=conditions)

    def search(self, collection_name, query_vector, top_k=5, metadata_filter=None):
        query_filter = self._build_filter(metadata_filter)
        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter
        ).points

        return [
            {
                "text": r.payload["text"],
                "metadata": r.payload["metadata"],
                "score": r.score
            }
            for r in results
        ]

    def delete_collection(self, name):
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]
        if name in existing:
            self.client.delete_collection(collection_name=name)
