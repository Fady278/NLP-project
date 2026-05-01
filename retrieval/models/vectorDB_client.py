import os
import hashlib
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
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

        try:
            self.client.get_collections()
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Qdrant: {e}")

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

    def collection_has_points(self, collection_name) -> bool:
        try:
            info = self.client.get_collection(collection_name)
        except Exception:
            return False
        return bool(getattr(info, "points_count", 0))

    def collection_exists(self, collection_name) -> bool:
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False

    def _normalize_point_id(self, point_id):
        if isinstance(point_id, int):
            return point_id

        point_id = str(point_id).strip()
        if point_id.isdigit():
            return int(point_id)

        digest = hashlib.sha256(point_id.encode("utf-8")).hexdigest()
        return str(uuid.UUID(digest[:32]))

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
            "metadata.file_hash",
            "metadata.chunk_content_hash",
            "metadata.document_group_id",
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
            point_ids = [meta.get("chunk_id") for meta in metadata]

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
            if isinstance(value, (list, tuple, set)):
                values = [item for item in value if item not in (None, "")]
                if not values:
                    continue
                match = MatchValue(value=values[0]) if len(values) == 1 else MatchAny(any=values)
            else:
                if value in (None, ""):
                    continue
                match = MatchValue(value=value)
            conditions.append(
                FieldCondition(
                    key=f"metadata.{key}",
                    match=match
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

    def get_existing_ids(self, collection_name) -> set:
        try:
            result = self.client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_vectors=False
            )
            existing_ids = set()
            for point in result[0]:
                existing_ids.add(point.id)
            return existing_ids
        except Exception:
            return set()

    def get_points_by_ids(self, collection_name, point_ids) -> dict:
        if not point_ids:
            return {}

        try:
            normalized_ids = [self._normalize_point_id(point_id) for point_id in point_ids]
            points = self.client.retrieve(
                collection_name=collection_name,
                ids=normalized_ids,
                with_payload=True,
                with_vectors=False,
            )
            return {point.id: point.payload for point in points}
        except Exception:
            return {}

    def list_point_ids(self, collection_name, metadata_filter=None) -> set:
        point_ids = set()
        next_offset = None
        query_filter = self._build_filter(metadata_filter)

        while True:
            points, next_offset = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                with_payload=False,
                with_vectors=False,
                limit=256,
                offset=next_offset,
            )
            for point in points:
                point_ids.add(point.id)
            if next_offset is None:
                break

        return point_ids

    def delete_points(self, collection_name, point_ids) -> int:
        normalized_ids = [self._normalize_point_id(point_id) for point_id in point_ids]
        normalized_ids = list(dict.fromkeys(normalized_ids))
        if not normalized_ids:
            return 0

        self.client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=normalized_ids),
            wait=True,
        )
        return len(normalized_ids)
