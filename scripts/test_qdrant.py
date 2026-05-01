import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval.models.vectorDB_client import VectorDBClient
from retrieval.models.embedding_model import EmbeddingModel

vectordb = VectorDBClient()
embedding_model = EmbeddingModel()

collection_name = "collection_local_test"

# ── 1. Check collection exists ──────────────────────────────
try:
    info = vectordb.client.get_collection(collection_name)
    print("Collection found!")
    print(f"   Vectors stored : {info.points_count}")
    print(f"   Vector size    : {info.config.params.vectors.size}")
except Exception as e:
    print(f"Collection not found: {e}")
    exit()

# ── 2. Check vector size is correct ────────────────────────
expected_size = 768  # multilingual-e5-base
actual_size = info.config.params.vectors.size
if actual_size == expected_size:
    print(f"Vector size correct: {actual_size}")
else:
    print(f"Vector size mismatch: expected {expected_size}, got {actual_size}")

# ── 3. Test semantic search ─────────────────────────────────
query = "enter your query hena"  # ← replace with something from your docs
query_vector = embedding_model.embed(query, doc_type="query")

results = vectordb.search(collection_name, query_vector, top_k=3)

if results:
    print(f"\n Search working! Top {len(results)} results for: '{query}'")
    print("=" * 60)
    for i, r in enumerate(results, 1):
        print(f"\n Result {i} | Score: {r['score']:.4f} | Page: {r['metadata'].get('page_label', 'N/A')}")
        print(f"Text   : {r['text'][:300]}...")
        print("-" * 60)
else:
    print("Search returned no results")