"""
Qdrant smoke test
-----------------
Validates that retrieval infrastructure can connect and perform a basic search
when Qdrant configuration and embedding dependencies are available.

Behavior:
- cleanly skips if Qdrant config is missing
- cleanly skips if collection name is not provided
- cleanly skips if optional retrieval dependencies are not installed
- checks collection existence and vector size
- runs a deterministic semantic search query
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


import pytest

def test_qdrant_smoke():
    _load_local_env()

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_api_key_file = os.getenv("QDRANT_API_KEY_FILE")
    collection_name = os.getenv("QDRANT_SMOKE_COLLECTION")
    query = os.getenv("QDRANT_SMOKE_QUERY", "enter your query hena")
    top_k = int(os.getenv("QDRANT_SMOKE_TOP_K", "3"))
    metadata_filter = {}

    smoke_lang = os.getenv("QDRANT_SMOKE_LANG")
    smoke_file_type = os.getenv("QDRANT_SMOKE_FILE_TYPE")
    smoke_strategy = os.getenv("QDRANT_SMOKE_STRATEGY")

    if smoke_lang:
        metadata_filter["lang"] = smoke_lang
    if smoke_file_type:
        metadata_filter["file_type"] = smoke_file_type
    if smoke_strategy:
        metadata_filter["strategy"] = smoke_strategy

    if not qdrant_url and not os.getenv("QDRANT_HOST"):
        pytest.skip("No Qdrant connection config found.")

    if not qdrant_api_key and not qdrant_api_key_file and qdrant_url:
        pytest.skip("Qdrant cloud URL is set, but no API key configuration was provided.")

    if not collection_name:
        pytest.skip("Set QDRANT_SMOKE_COLLECTION to run the Qdrant smoke test.")

    try:
        from retrieval.models.vectorDB_client import VectorDBClient
        from retrieval.models.embedding_model import EmbeddingModel
    except ModuleNotFoundError as exc:
        pytest.skip(f"Missing optional retrieval dependency: {exc}")

    try:
        vectordb = VectorDBClient()
        embedding_model = EmbeddingModel()
    except Exception as exc:
        pytest.fail(f"FAILED: Unable to initialize retrieval stack: {exc}")

    try:
        info = vectordb.client.get_collection(collection_name)
    except Exception as exc:
        pytest.fail(f"FAILED: Collection '{collection_name}' is not accessible: {exc}")

    print("Collection found!")
    print(f"   Name          : {collection_name}")
    print(f"   Vectors stored: {info.points_count}")
    print(f"   Vector size   : {info.config.params.vectors.size}")

    expected_size = embedding_model.embedding_size
    actual_size = info.config.params.vectors.size
    assert actual_size == expected_size, f"FAILED: Vector size mismatch: expected {expected_size}, got {actual_size}"

    query_vector = embedding_model.embed(query, doc_type="query")
    try:
        results = vectordb.search(
            collection_name,
            query_vector,
            top_k=top_k,
            metadata_filter=metadata_filter or None,
        )
    except Exception as exc:
        pytest.fail(f"FAILED: Search request failed: {exc}")

    assert results, "FAILED: Search returned no results."

    print(f"\nSearch working! Top {len(results)} result(s) for: '{query}'")
    if metadata_filter:
        print(f"Applied metadata filter: {metadata_filter}")
    print("=" * 60)
    for i, result in enumerate(results, 1):
        print(f"\nResult {i} | Score: {result['score']:.4f}")
        print(f"Chunk ID: {result['metadata'].get('chunk_id', 'N/A')}")
        print(f"Text   : {result['text'][:240]}...")
        print("-" * 60)


