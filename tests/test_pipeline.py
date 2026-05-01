"""
test_pipeline.py
----------------
Quick smoke-test that validates the preprocessing pipeline works
end-to-end without needing real documents.

Run from the project root:
    python tests/test_pipeline.py
"""

import hashlib
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# Make sure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocessing.cleaners.text_cleaner import TextCleaner
from preprocessing.loaders.html_loader import HTMLLoader
from preprocessing.models.document import RawDocument, save_documents, load_documents
from preprocessing.pipeline import PreprocessingPipeline


def _get_indexing_service():
    from retrieval.services.indexing_service import IndexingService

    return IndexingService


def _get_retrieval_service():
    from retrieval.services.retrieval_service import RetrievalService

    return RetrievalService


def _state_path(tmpdir: str) -> Path:
    return Path(tmpdir) / "index_state.sqlite3"


# -----------------------------------------------------------------------
# Test 1 — Raw document model + serialisation
# -----------------------------------------------------------------------
def test_document_model():
    print("\n--- Test 1: Document model ---")
    raw = RawDocument(
        source_path="/tmp/sample.pdf",
        file_type="pdf",
        page_num=0,
        raw_text="Hello world. This is a test document.",
        metadata={"pdf_title": "Sample"},
    )
    print(f"  doc_id  : {raw.doc_id}")
    print(f"  raw_text: {raw.raw_text[:60]}")
    assert raw.doc_id, "doc_id must not be empty"
    assert raw.metadata["identity_fallback"] == "content_hash"


# -----------------------------------------------------------------------
# Test 2 — TextCleaner on English text
# -----------------------------------------------------------------------
def test_cleaner_english():
    print("\n--- Test 2: TextCleaner (English) ---")
    cleaner = TextCleaner()
    raw = RawDocument(
        source_path="/tmp/en.pdf",
        file_type="pdf",
        page_num=0,
        raw_text="This  is   a  messy\x00\x01 text  with  \t extra\tspaces.\nAnd a PDF hy-\nphen-ated word.\n\n\n\nToo many blank lines.",
    )
    clean = cleaner.clean(raw)
    print(f"  lang    : {clean.detected_lang}")
    print(f"  words   : {clean.word_count}")
    print(f"  text    : {clean.clean_text[:120]}")
    assert clean.detected_lang == "en"
    assert "\x00" not in clean.clean_text
    assert "  " not in clean.clean_text  # no double spaces


# -----------------------------------------------------------------------
# Test 3 — TextCleaner on Arabic text
# -----------------------------------------------------------------------
def test_cleaner_arabic():
    print("\n--- Test 3: TextCleaner (Arabic) ---")
    cleaner = TextCleaner(remove_arabic_diacritics=True)
    arabic_text = (
        "السيرة الذاتية لمحمد أحمد\n"
        "أعمل مطوراً في مجال الذكاء الاصطناعي.\n"
        "لديَّ خبرة في معالجة اللغة الطبيعية والتعلم الآلي.\n"
        "أَبْحَثُ عَنْ فُرَصٍ جَدِيدَةٍ."          # has tashkeel → should be removed
    )
    raw = RawDocument(
        source_path="/tmp/arabic_cv.pdf",
        file_type="pdf",
        page_num=0,
        raw_text=arabic_text,
    )
    clean = cleaner.clean(raw)
    print(f"  lang      : {clean.detected_lang}")
    print(f"  is_arabic : {clean.is_arabic}")
    print(f"  arabic %  : {clean.metadata['arabic_char_ratio']:.0%}")
    print(f"  words     : {clean.word_count}")
    print(f"  text[:80] : {clean.clean_text[:80]}")
    assert clean.is_arabic, "Arabic text should be detected as Arabic"
    assert clean.detected_lang == "ar"


# -----------------------------------------------------------------------
# Test 4 — HTMLLoader + cleaner integration
# -----------------------------------------------------------------------
def test_html_loader():
    print("\n--- Test 4: HTMLLoader ---")
    html = """<!DOCTYPE html>
<html>
<head><title>Job Posting: ML Engineer</title></head>
<body>
  <nav>Skip this nav bar</nav>
  <article>
    <h1>Machine Learning Engineer</h1>
    <p>We are looking for an experienced ML Engineer to join our team.</p>
    <p>Requirements: Python, PyTorch, 3+ years of experience.</p>
  </article>
  <aside>Irrelevant sidebar content</aside>
  <script>alert('ignore me')</script>
</body>
</html>"""
    loader = HTMLLoader.from_string(html, virtual_path="job_posting.html")
    raw_docs = loader.load()
    print(f"  sections loaded: {len(raw_docs)}")

    cleaner = TextCleaner()
    clean_docs = [cleaner.clean(r) for r in raw_docs]
    non_empty = [d for d in clean_docs if not d.is_empty()]
    print(f"  non-empty after cleaning: {len(non_empty)}")
    assert len(non_empty) >= 1
    assert len(raw_docs[0].file_hash) == 64


# -----------------------------------------------------------------------
# Test 5 — Full pipeline with temp PDF
# -----------------------------------------------------------------------
def test_pipeline_pdf():
    import pytest
    pdf_src = Path(__file__).resolve().parent.parent / "data" / "raw" / "NLP_RAG_Project.pdf"
    if not pdf_src.exists():
        pytest.skip("Skipped (project PDF not found in data/raw)")

    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy(pdf_src, Path(tmpdir) / "NLP_RAG_Project.pdf")
        pipeline = PreprocessingPipeline(output_dir=Path(tmpdir) / "out", min_words=3)
        docs = pipeline.run_directory(tmpdir, extensions=["pdf"])

    assert len(docs) > 0, "Expected at least one document"


def test_pipeline_writes_latest_and_snapshot_outputs():
    raw = RawDocument(
        source_path="/tmp/test.pdf",
        file_type="pdf",
        page_num=0,
        raw_text="This is a stable test document with enough words to chunk correctly.",
        file_hash="fixed-hash",
    )

    class DummyLoader:
        file_hash = "fixed-hash"

        def load(self):
            return [raw]

    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = PreprocessingPipeline(output_dir=tmpdir, min_words=3)
        with patch("preprocessing.pipeline.get_loader", return_value=DummyLoader()):
            pipeline.run([Path("doc.pdf")])

        out_dir = Path(tmpdir)
        assert (out_dir / "clean_documents.jsonl").exists()
        assert (out_dir / f"clean_documents__{pipeline.ingestion_id}.jsonl").exists()
        assert (out_dir / "chunks_sentence_window.jsonl").exists()
        assert (out_dir / f"chunks_sentence_window__{pipeline.ingestion_id}.jsonl").exists()


# -----------------------------------------------------------------------
# Test 6 — Save / load round-trip
# -----------------------------------------------------------------------
def test_serialisation():
    print("\n--- Test 6: Save/Load round-trip ---")
    cleaner = TextCleaner()
    raw = RawDocument(
        source_path="/tmp/test.pdf",
        file_type="pdf",
        page_num=2,
        raw_text="Round-trip serialisation test. The quick brown fox.",
    )
    clean = cleaner.clean(raw)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp_path = f.name
    save_documents([clean], tmp_path)
    loaded = load_documents(tmp_path)

    assert len(loaded) == 1
    assert loaded[0].doc_id == clean.doc_id
    assert loaded[0].clean_text == clean.clean_text
    print(f"  Round-trip OK — doc_id: {loaded[0].doc_id}")


def test_clean_document_keeps_stable_source_identity():
    raw = RawDocument(
        source_path="/tmp/stable.pdf",
        file_type="pdf",
        page_num=1,
        raw_text="Original raw text",
        file_hash="fixed-file-hash",
    )
    cleaner = TextCleaner()
    clean = cleaner.clean(raw)

    assert clean.doc_id == raw.doc_id
    assert clean.metadata["file_hash"] == raw.file_hash
    assert clean.metadata["content_hash"]


def test_pipeline_skips_loader_failure():
    class BrokenLoader:
        file_hash = "broken-file-hash"

        def load(self):
            raise OSError("corrupt file")

    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = PreprocessingPipeline(output_dir=tmpdir)
        fake_path = Path("broken.pdf")

        with patch("preprocessing.pipeline.get_loader", return_value=BrokenLoader()):
            docs = pipeline.run([fake_path])

    assert docs == []


def test_pipeline_skips_duplicate_files_before_load():
    class DummyLoader:
        def __init__(self, file_hash, docs):
            self.file_hash = file_hash
            self._docs = docs

        def load(self):
            return self._docs

    raw_doc = RawDocument(
        source_path="/tmp/a.pdf",
        file_type="pdf",
        page_num=0,
        raw_text="Same file contents with enough words to survive cleaning.",
        file_hash="shared-file-hash",
    )
    loaders = [
        DummyLoader("shared-file-hash", [raw_doc]),
        DummyLoader("shared-file-hash", [raw_doc]),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = PreprocessingPipeline(output_dir=tmpdir)
        with patch("preprocessing.pipeline.get_loader", side_effect=loaders):
            docs = pipeline.run([Path("first.pdf"), Path("second.pdf")])

    assert len(docs) == 1


def test_indexing_service_uses_chunk_ids_and_deduplicates():
    class FakeEmbeddingModel:
        embedding_size = 3
        cache_namespace = "fake-model|v1"

        def embed_batch(self, texts, doc_type="passage"):
            return [[0.1, 0.2, 0.3] for _ in texts]

    class FakeVectorDBClient:
        def __init__(self):
            self.deleted = []
            self.created = []
            self.added = None

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def delete_collection(self, collection_name):
            self.deleted.append(collection_name)

        def create_collection(self, collection_name, embedding_size):
            self.created.append((collection_name, embedding_size))

        def add_documents(self, **kwargs):
            self.added = kwargs

    class DummyChunk:
        def __init__(self, chunk_id, text, source_doc_id, file_hash="file-1"):
            self.chunk_id = chunk_id
            self.text = text
            self.source_doc_id = source_doc_id
            self.source_path = "/tmp/doc.pdf"
            self.file_type = "pdf"
            self.page_num = 0
            self.strategy = "sentence_window"
            self.metadata = {
                "document_group_id": source_doc_id,
                "file_hash": file_hash,
                "chunk_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        client = FakeVectorDBClient()
        service = _get_indexing_service()(client, FakeEmbeddingModel(), state_path=_state_path(tmpdir))
        chunks = [
            DummyChunk("chunk-1", "same text", "doc-1"),
            DummyChunk("chunk-1", "same text", "doc-1"),
            DummyChunk("chunk-2", "other text", "doc-1"),
        ]

        service.push_data_to_index(type("Project", (), {"id": "demo"})(), chunks, do_reset=False)

        assert client.deleted == []
        assert client.created == [("collection_demo", 3)]
        assert client.added["point_ids"] == ["chunk-1", "chunk-2"]
        assert client.added["texts"] == ["same text", "other text"]


def test_indexing_service_skip_existing_filters_before_embedding():
    class FakeEmbeddingModel:
        embedding_size = 3
        cache_namespace = "fake-model|v1"

        def __init__(self):
            self.calls = []

        def embed_batch(self, texts, doc_type="passage"):
            self.calls.append(list(texts))
            return [[0.1, 0.2, 0.3] for _ in texts]

    class FakeVectorDBClient:
        def __init__(self):
            self.added = None

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def create_collection(self, collection_name, embedding_size):
            return None

        def add_documents(self, **kwargs):
            self.added = kwargs

    class DummyChunk:
        def __init__(self, chunk_id, text, source_doc_id):
            self.chunk_id = chunk_id
            self.text = text
            self.source_doc_id = source_doc_id
            self.source_path = "/tmp/doc.pdf"
            self.file_type = "pdf"
            self.page_num = 0
            self.strategy = "sentence_window"
            self.metadata = {
                "file_hash": "file-1",
                "chunk_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "document_group_id": source_doc_id,
                "ingestion_id": "ing-1",
                "ingested_at": "2026-05-01T00:00:00",
                "first_ingested_at": "2026-05-01T00:00:00",
                "last_ingested_at": "2026-05-01T00:00:00",
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        client = FakeVectorDBClient()
        embedding = FakeEmbeddingModel()
        service = _get_indexing_service()(client, embedding, state_path=_state_path(tmpdir))
        project = type("Project", (), {"id": "demo"})()
        initial_chunks = [DummyChunk("chunk-1", "existing text", "doc-1")]
        service.push_data_to_index(project, initial_chunks, do_reset=False)

        client.added = None
        service.push_data_to_index(
            project,
            [
                DummyChunk("chunk-1", "existing text", "doc-1"),
                DummyChunk("chunk-2", "new text", "doc-1"),
            ],
            do_reset=False,
        )

        assert embedding.calls == [["existing text"], ["new text"]]
        assert client.added["point_ids"] == ["chunk-2"]


def test_indexing_service_deduplicates_by_hashed_text_key():
    class FakeEmbeddingModel:
        embedding_size = 2
        cache_namespace = "fake-model|v1"

        def embed_batch(self, texts, doc_type="passage"):
            return [[0.1, 0.2] for _ in texts]

    class FakeVectorDBClient:
        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def create_collection(self, collection_name, embedding_size):
            return None

        def add_documents(self, **kwargs):
            self.kwargs = kwargs

    class DummyChunk:
        def __init__(self, chunk_id, text, source_doc_id):
            self.chunk_id = chunk_id
            self.text = text
            self.source_doc_id = source_doc_id
            self.source_path = "/tmp/doc.pdf"
            self.file_type = "pdf"
            self.page_num = 0
            self.strategy = "sentence_window"
            self.metadata = {
                "file_hash": "file-1",
                "chunk_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "document_group_id": source_doc_id,
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        client = FakeVectorDBClient()
        service = _get_indexing_service()(client, FakeEmbeddingModel(), state_path=_state_path(tmpdir))
        long_text = "duplicate text " * 200
        chunks = [
            DummyChunk("chunk-1", long_text, "doc-1"),
            DummyChunk("chunk-2", long_text, "doc-1"),
        ]

        service.push_data_to_index(type("Project", (), {"id": "demo"})(), chunks, do_reset=False)

        assert client.kwargs["point_ids"] == ["chunk-1", "chunk-2"]


def test_indexing_service_removes_stale_points_for_updated_file_hash():
    class FakeEmbeddingModel:
        embedding_size = 2
        cache_namespace = "fake-model|v1"

        def embed_batch(self, texts, doc_type="passage"):
            return [[0.1, 0.2] for _ in texts]

    class FakeVectorDBClient:
        def __init__(self):
            self.deleted_ids = []
            self.kwargs = None

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def create_collection(self, collection_name, embedding_size):
            return None

        def delete_points(self, collection_name, point_ids):
            self.deleted_ids.extend(sorted(point_ids))
            return len(point_ids)

        def add_documents(self, **kwargs):
            self.kwargs = kwargs

    class DummyChunk:
        def __init__(self, chunk_id, text):
            self.chunk_id = chunk_id
            self.text = text
            self.source_doc_id = "doc-1"
            self.source_path = "/tmp/doc.pdf"
            self.file_type = "pdf"
            self.page_num = 0
            self.strategy = "sentence_window"
            self.metadata = {
                "file_hash": "file-1",
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "chunk_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "document_group_id": "doc-1",
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        client = FakeVectorDBClient()
        service = _get_indexing_service()(client, FakeEmbeddingModel(), state_path=_state_path(tmpdir))
        project = type("Project", (), {"id": "demo"})()
        service.push_data_to_index(
            project,
            [DummyChunk("chunk-old", "old text")],
            do_reset=False,
        )

        client.deleted_ids = []
        service.push_data_to_index(
            project,
            [DummyChunk("chunk-new", "updated text")],
            do_reset=False,
        )

        assert client.deleted_ids == ["chunk-old"]
        assert client.kwargs["point_ids"] == ["chunk-new"]


def test_indexing_service_reuses_embedding_cache_for_same_content_across_files():
    class FakeEmbeddingModel:
        embedding_size = 2
        cache_namespace = "fake-model|v1"

        def __init__(self):
            self.calls = []

        def embed_batch(self, texts, doc_type="passage"):
            self.calls.append(list(texts))
            return [[0.1, 0.2] for _ in texts]

    class FakeVectorDBClient:
        def __init__(self):
            self.calls = []

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def create_collection(self, collection_name, embedding_size):
            return None

        def add_documents(self, **kwargs):
            self.calls.append(kwargs)

    class DummyChunk:
        def __init__(self, chunk_id, source_path):
            text = "shared content"
            self.chunk_id = chunk_id
            self.text = text
            self.source_doc_id = chunk_id
            self.source_path = source_path
            self.file_type = "pdf"
            self.page_num = 0
            self.strategy = "sentence_window"
            self.metadata = {
                "file_hash": chunk_id,
                "chunk_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "document_group_id": chunk_id,
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        embedding = FakeEmbeddingModel()
        client = FakeVectorDBClient()
        service = _get_indexing_service()(client, embedding, state_path=_state_path(tmpdir))
        service.push_data_to_index(
            type("Project", (), {"id": "demo"})(),
            [DummyChunk("file-a", "/tmp/a.pdf"), DummyChunk("file-b", "/tmp/b.pdf")],
            do_reset=False,
        )

        assert embedding.calls == [["shared content"]]
        assert len(client.calls[0]["point_ids"]) == 2


def test_indexing_service_ignores_volatile_ingestion_metadata_for_unchanged_content():
    class FakeEmbeddingModel:
        embedding_size = 2
        cache_namespace = "fake-model|v1"

        def __init__(self):
            self.calls = []

        def embed_batch(self, texts, doc_type="passage"):
            self.calls.append(list(texts))
            return [[0.1, 0.2] for _ in texts]

    class FakeVectorDBClient:
        def __init__(self):
            self.calls = []

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def create_collection(self, collection_name, embedding_size):
            return None

        def add_documents(self, **kwargs):
            self.calls.append(kwargs)

        def delete_points(self, collection_name, point_ids):
            return len(point_ids)

    class DummyChunk:
        def __init__(self, chunk_id, ingested_at):
            text = "stable content"
            self.chunk_id = chunk_id
            self.text = text
            self.source_doc_id = "doc-1"
            self.source_path = "/tmp/doc.pdf"
            self.file_type = "pdf"
            self.page_num = 0
            self.strategy = "sentence_window"
            self.metadata = {
                "file_hash": "file-1",
                "chunk_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "document_group_id": "doc-1",
                "ingestion_id": f"ing-{ingested_at}",
                "ingested_at": ingested_at,
                "last_ingested_at": ingested_at,
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        embedding = FakeEmbeddingModel()
        client = FakeVectorDBClient()
        service = _get_indexing_service()(client, embedding, state_path=_state_path(tmpdir))
        project = type("Project", (), {"id": "demo"})()

        service.push_data_to_index(project, [DummyChunk("chunk-1", "2026-05-01T00:00:00")], do_reset=False)
        first_call_count = len(client.calls)

        service.push_data_to_index(project, [DummyChunk("chunk-1", "2026-05-02T00:00:00")], do_reset=False)

        assert embedding.calls == [["stable content"]]
        assert len(client.calls) == first_call_count


def test_sentence_window_chunks_do_not_duplicate_overlap_text_when_merging_is_disabled():
    raw = RawDocument(
        source_path="/tmp/sample.pdf",
        file_type="pdf",
        page_num=0,
        raw_text="One. Two. Three. Four. Five. Six.",
        file_hash="file-hash",
    )
    clean = TextCleaner().clean(raw)
    chunks = __import__("preprocessing.chunking", fromlist=["chunk_by_sentence_window"]).chunk_by_sentence_window(
        clean,
        target_tokens=3,
        overlap_sentences=1,
    )

    assert len(chunks) >= 2
    assert chunks[0].text != chunks[1].text


def test_retrieval_service_prefers_exact_dedup_before_semantic_fallback_and_respects_top_k():
    class FakeEmbeddingModel:
        def __init__(self):
            self.query_calls = 0
            self.batch_calls = 0

        def embed(self, text, doc_type="query"):
            self.query_calls += 1
            return [0.1, 0.2]

        def embed_batch(self, texts, doc_type="passage"):
            self.batch_calls += 1
            raise AssertionError("retrieval should not re-embed result chunks")

    class FakeVectorDBClient:
        def __init__(self):
            self.search_calls = 0

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def search(self, collection_name, query_vector, top_k=5, metadata_filter=None):
            self.search_calls += 1
            base = [
                {"text": "alpha", "metadata": {"chunk_id": "c1", "chunk_content_hash": "h1"}, "score": 0.99},
                {"text": "alpha", "metadata": {"chunk_id": "c1", "chunk_content_hash": "h1"}, "score": 0.98},
                {"text": "beta", "metadata": {"chunk_id": "c2", "chunk_content_hash": "h2"}, "score": 0.97},
                {"text": "gamma", "metadata": {"chunk_id": "c3", "chunk_content_hash": "h3"}, "score": 0.96},
                {"text": "delta", "metadata": {"chunk_id": "c4", "chunk_content_hash": "h4"}, "score": 0.95},
            ]
            return base[:top_k]

    client = FakeVectorDBClient()
    embedding = FakeEmbeddingModel()
    service = _get_retrieval_service()(client, embedding)
    results = service.search("demo", "query", top_k=3, dedup=True)

    assert len(results) == 3
    assert [r["metadata"]["chunk_id"] for r in results] == ["c1", "c2", "c3"]
    assert client.search_calls == 1
    assert embedding.query_calls == 1
    assert embedding.batch_calls == 0


def test_retrieval_service_scans_all_candidates_before_truncating_top_k():
    class FakeEmbeddingModel:
        def __init__(self):
            self.batch_calls = 0

        def embed(self, text, doc_type="query"):
            return [0.1, 0.2]

        def embed_batch(self, texts, doc_type="passage"):
            self.batch_calls += 1
            raise AssertionError("retrieval should not re-embed result chunks")

    class FakeVectorDBClient:
        def __init__(self):
            self.search_calls = 0

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def search(self, collection_name, query_vector, top_k=5, metadata_filter=None):
            self.search_calls += 1
            return [
                {"text": "dup-a", "metadata": {"chunk_id": "c1", "chunk_content_hash": "h1"}, "score": 0.99},
                {"text": "dup-a", "metadata": {"chunk_id": "c1", "chunk_content_hash": "h1"}, "score": 0.98},
                {"text": "dup-b", "metadata": {"chunk_id": "c2", "chunk_content_hash": "h2"}, "score": 0.97},
                {"text": "dup-b", "metadata": {"chunk_id": "c2", "chunk_content_hash": "h2"}, "score": 0.96},
                {"text": "unique-c", "metadata": {"chunk_id": "c3", "chunk_content_hash": "h3"}, "score": 0.95},
                {"text": "unique-d", "metadata": {"chunk_id": "c4", "chunk_content_hash": "h4"}, "score": 0.94},
            ][:top_k]

    client = FakeVectorDBClient()
    embedding = FakeEmbeddingModel()
    service = _get_retrieval_service()(client, embedding)
    results = service.search("demo", "query", top_k=3, dedup=True)

    assert [r["metadata"]["chunk_id"] for r in results] == ["c1", "c2", "c3"]
    assert client.search_calls == 1
    assert embedding.batch_calls == 0


def test_retrieval_service_large_top_k_is_still_single_query():
    class FakeEmbeddingModel:
        def __init__(self):
            self.query_calls = 0

        def embed(self, text, doc_type="query"):
            self.query_calls += 1
            return [0.1, 0.2]

    class FakeVectorDBClient:
        def __init__(self):
            self.search_calls = 0

        def create_collection_name(self, project_id):
            return f"collection_{project_id}"

        def search(self, collection_name, query_vector, top_k=5, metadata_filter=None):
            self.search_calls += 1
            return [
                {
                    "text": f"text-{i}",
                    "metadata": {
                        "chunk_id": f"c{i}",
                        "chunk_content_hash": f"h{i}",
                    },
                    "score": 1.0 - i * 0.001,
                }
                for i in range(top_k)
            ]

    client = FakeVectorDBClient()
    embedding = FakeEmbeddingModel()
    service = _get_retrieval_service()(client, embedding)
    results = service.search("demo", "query", top_k=100, dedup=True)

    assert len(results) == 100
    assert client.search_calls == 1
    assert embedding.query_calls == 1
