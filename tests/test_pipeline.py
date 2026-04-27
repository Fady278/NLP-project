"""
test_pipeline.py
----------------
Quick smoke-test that validates the preprocessing pipeline works
end-to-end without needing real documents.

Run from the project root:
    python tests/test_pipeline.py
"""

import logging
import sys
import tempfile
from pathlib import Path

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
    print("  PASSED ✓")


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
    print("  PASSED ✓")


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
    print("  PASSED ✓")


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
    for d in raw_docs:
        print(f"    page {d.page_num} | chars {len(d.raw_text)} | meta: {d.metadata.get('section_title','')}")

    cleaner = TextCleaner()
    clean_docs = [cleaner.clean(r) for r in raw_docs]
    non_empty = [d for d in clean_docs if not d.is_empty()]
    print(f"  non-empty after cleaning: {len(non_empty)}")
    assert len(non_empty) >= 1
    print("  PASSED ✓")


# -----------------------------------------------------------------------
# Test 5 — Full pipeline with temp PDF
# -----------------------------------------------------------------------
def test_pipeline_pdf():
    print("\n--- Test 5: Pipeline with real PDF ---")
    import shutil

    pdf_src = Path("/mnt/user-data/uploads/NLP_RAG_Project.pdf")
    if not pdf_src.exists():
        print("  Skipped (no uploaded PDF in environment)")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy(pdf_src, Path(tmpdir) / "NLP_RAG_Project.pdf")
        pipeline = PreprocessingPipeline(output_dir=Path(tmpdir) / "out", min_words=3)
        docs = pipeline.run_directory(tmpdir, extensions=["pdf"])

    print(f"  clean documents: {len(docs)}")
    for d in docs:
        print(
            f"    page {d.page_num:02d} | {d.word_count:4d} words "
            f"| lang={d.detected_lang} | arabic={d.is_arabic} "
            f"| {d.clean_text[:60]!r}…"
        )
    assert len(docs) > 0, "Expected at least one document"
    print("  PASSED ✓")


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
    print("  PASSED ✓")


# -----------------------------------------------------------------------
# Run all tests
# -----------------------------------------------------------------------
if __name__ == "__main__":
    tests = [
        test_document_model,
        test_cleaner_english,
        test_cleaner_arabic,
        test_html_loader,
        test_pipeline_pdf,
        test_serialisation,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            print(f"  FAILED ✗ — {exc}")
            failures += 1

    print(f"\n{'='*40}")
    print(f"  {len(tests) - failures}/{len(tests)} tests passed.")
    print(f"{'='*40}\n")
    sys.exit(failures)
