from __future__ import annotations

import argparse
import logging
import re
import statistics
from pathlib import Path

from preprocessing.chunking import chunk_documents
from preprocessing.pipeline import PreprocessingPipeline

TARGET_MIN_TOKENS = 80
TARGET_MAX_TOKENS = 250
HARD_MAX_TOKENS = 512
QUERY_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare chunking strategies for Person 1.")
    parser.add_argument("--input-dir", default="data/raw", help="Directory with raw documents (default: data/raw).")
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory to write chunking_comparison.md",
    )
    parser.add_argument(
        "--extensions",
        default="pdf,docx,html,htm",
        help="Comma-separated file extensions to process.",
    )
    parser.add_argument("--min-words", type=int, default=5)
    parser.add_argument(
        "--query-file",
        default="",
        help="Optional text file with one evaluation query per line for a lightweight retrieval comparison.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser


def summarize(chunks: list) -> dict:
    if not chunks:
        return {}
    token_counts = [chunk.token_count for chunk in chunks]
    avg = statistics.mean(token_counts)
    stdev = statistics.stdev(token_counts) if len(token_counts) > 1 else 0.0

    # Split by language
    ar_tokens = [c.token_count for c in chunks if c.metadata.get("is_arabic")]
    en_tokens = [c.token_count for c in chunks if not c.metadata.get("is_arabic")]
    tiny_count = sum(1 for t in token_counts if t < TARGET_MIN_TOKENS)
    in_range_count = sum(1 for t in token_counts if TARGET_MIN_TOKENS <= t <= TARGET_MAX_TOKENS)
    oversize_count = sum(1 for t in token_counts if t > TARGET_MAX_TOKENS)
    hard_oversize_count = sum(1 for t in token_counts if t > HARD_MAX_TOKENS)
    doc_count = len({c.source_doc_id for c in chunks})
    variation_ratio = round((stdev / avg), 3) if avg > 0 else 0.0

    return {
        "count": len(chunks),
        "avg": round(avg, 1),
        "median": int(statistics.median(token_counts)),
        "max": max(token_counts),
        "min": min(token_counts),
        "stdev": round(stdev, 1),
        "variation_ratio": variation_ratio,
        "total_tokens": sum(token_counts),
        "ar_count": len(ar_tokens),
        "en_count": len(en_tokens),
        "doc_count": doc_count,
        "tiny_count": tiny_count,
        "in_range_count": in_range_count,
        "oversize_count": oversize_count,
        "hard_oversize_count": hard_oversize_count,
        "in_range_pct": round((in_range_count / len(chunks)) * 100, 1),
    }


def summarize_dataset(clean_docs: list) -> dict:
    source_files = {doc.source_path for doc in clean_docs}
    file_type_counts: dict[str, int] = {}
    arabic_docs = 0
    for doc in clean_docs:
        file_type_counts[doc.file_type] = file_type_counts.get(doc.file_type, 0) + 1
        if doc.is_arabic:
            arabic_docs += 1
    return {
        "source_file_count": len(source_files),
        "clean_doc_count": len(clean_docs),
        "arabic_doc_count": arabic_docs,
        "file_type_counts": file_type_counts,
    }


def _query_terms(query: str) -> set[str]:
    return {term.lower() for term in QUERY_TOKEN_RE.findall(query) if len(term) > 2}


def run_retrieval_probe(chunks: list, query_file: str) -> dict | None:
    query_path = Path(query_file)
    if not query_file or not query_path.exists():
        return None

    queries = [line.strip() for line in query_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not queries:
        return None

    hit_count = 0
    score_total = 0.0
    for query in queries:
        q_terms = _query_terms(query)
        if not q_terms:
            continue

        best_overlap = 0.0
        for chunk in chunks:
            c_terms = _query_terms(chunk.text)
            if not c_terms:
                continue
            overlap = len(q_terms & c_terms) / len(q_terms)
            if overlap > best_overlap:
                best_overlap = overlap
        score_total += best_overlap
        if best_overlap >= 0.5:
            hit_count += 1

    evaluated = len([q for q in queries if _query_terms(q)])
    if evaluated == 0:
        return None
    return {
        "query_count": evaluated,
        "avg_overlap": round(score_total / evaluated, 3),
        "hit_rate": round((hit_count / evaluated) * 100, 1),
    }


def score_strategy(stats: dict) -> float:
    """
    Size-based score only.
    Higher is better for embedding readiness, not retrieval quality.
    """
    if not stats:
        return float("-inf")
    score = 0.0
    score += stats["in_range_pct"] * 1.5
    score -= stats["tiny_count"] * 3.0
    score -= stats["oversize_count"] * 4.0
    score -= stats["hard_oversize_count"] * 8.0
    score -= stats["variation_ratio"] * 20.0
    return round(score, 2)


def generate_insights(results: dict[str, dict], dataset_summary: dict, retrieval_results: dict[str, dict] | None = None) -> list[str]:
    insights = ["## Data-Driven Insights", ""]

    if dataset_summary["source_file_count"] < 3:
        insights.append(
            f"- The current analysis is based on only {dataset_summary['source_file_count']} source file(s), so the result should be treated as preliminary until more domain documents are added."
        )
    if dataset_summary["arabic_doc_count"] == 0:
        insights.append(
            "- No Arabic documents were detected in the current sample, so Arabic-specific chunking behavior has not been validated yet."
        )
    insights.append("")

    for strategy, stats in results.items():
        if stats["hard_oversize_count"] > 0:
            insights.append(
                f"- `{strategy}` produced {stats['hard_oversize_count']} chunk(s) above {HARD_MAX_TOKENS} tokens, which risks truncation with smaller embedding models."
            )

        if stats["oversize_count"] > 0:
            insights.append(
                f"- `{strategy}` has {stats['oversize_count']} chunk(s) above the target range ({TARGET_MIN_TOKENS}-{TARGET_MAX_TOKENS} tokens)."
            )

        if stats["tiny_count"] > 0:
            insights.append(
                f"- `{strategy}` has {stats['tiny_count']} chunk(s) below {TARGET_MIN_TOKENS} tokens; very small chunks may lose surrounding context."
            )

        if stats["variation_ratio"] > 0.4:
            insights.append(
                f"- `{strategy}` has high size variability (std/avg = {stats['variation_ratio']}). This means chunk sizes are inconsistent across the dataset."
            )
        else:
            insights.append(
                f"- `{strategy}` is relatively uniform (std/avg = {stats['variation_ratio']}), which is good for stable embedding input sizes."
            )

    if "paragraph" in results and "sentence_window" in results:
        p = results["paragraph"]
        s = results["sentence_window"]
        p_score = score_strategy(p)
        s_score = score_strategy(s)
        insights.append("")
        insights.append("## Recommendation Basis")
        insights.append("")
        insights.append(
            f"- Size-based score — `paragraph`: {p_score}, `sentence_window`: {s_score}."
        )

        if p_score > s_score:
            insights.append(
                f"- Current dataset favors `paragraph` because it keeps more chunks inside the target range with fewer size penalties."
            )
        elif s_score > p_score:
            insights.append(
                f"- Current dataset favors `sentence_window` because it keeps chunk sizes tighter and reduces oversize chunks."
            )
        else:
            insights.append(
                "- Both strategies are very close by size metrics alone, so the final choice should be based on retrieval experiments in the next phase."
            )

    if retrieval_results:
        insights.append("")
        insights.append("## Optional Retrieval Probe")
        insights.append("")
        for strategy, probe in retrieval_results.items():
            insights.append(
                f"- `{strategy}` on {probe['query_count']} query/queries: hit rate {probe['hit_rate']}%, average lexical overlap {probe['avg_overlap']}."
            )
        insights.append(
            "- This probe is lightweight and lexical only, but it is closer to retrieval behavior than chunk-size statistics alone."
        )

    insights.append("")
    if retrieval_results:
        insights.append(
            "- Note: final justification should still be confirmed with the actual embedding model and vector store used in the full RAG pipeline."
        )
    else:
        insights.append(
            "- Note: this script compares chunk size quality only unless a query file is supplied. Final justification should also include retrieval behavior on real queries."
        )
    return insights


def render_markdown(results: dict[str, dict], dataset_summary: dict, retrieval_results: dict[str, dict] | None = None) -> str:
    type_summary = ", ".join(
        f"{file_type}:{count}" for file_type, count in sorted(dataset_summary["file_type_counts"].items())
    ) or "none"
    lines = [
        "# Chunking Strategy Analysis",
        "",
        f"This report evaluates chunking performance across **{dataset_summary['source_file_count']}** source file(s) and **{dataset_summary['clean_doc_count']}** processed clean document(s)/section(s).",
        "",
        f"File type breakdown: **{type_summary}**.",
        "",
        f"Target chunk range used for analysis: **{TARGET_MIN_TOKENS}-{TARGET_MAX_TOKENS} tokens**.",
        "",
        "## Performance Metrics",
        "",
        "| Strategy | Chunks | Avg Tokens | Median | Min | Max | StdDev | In Range % | Arabic/Eng |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for name, s in results.items():
        lang_mix = f"{s['ar_count']}/{s['en_count']}"
        lines.append(
            f"| `{name}` | {s['count']} | {s['avg']} | {s['median']} | {s['min']} | {s['max']} | {s['stdev']} | {s['in_range_pct']}% | {lang_mix} |"
        )

    lines.append("")
    lines.extend(generate_insights(results, dataset_summary, retrieval_results))

    lines.extend(["", "---", "*Report generated automatically from current dataset statistics.*"])
    return "\n".join(lines)


def main() -> None:
    args = build_arg_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    pipeline = PreprocessingPipeline(output_dir=args.output_dir, min_words=args.min_words)
    # Check if input dir exists
    input_path = Path(args.input_dir)
    if not input_path.exists():
        logging.error(f"Input directory not found: {args.input_dir}")
        return

    clean_docs = pipeline.run_directory(args.input_dir, args.extensions.split(","))
    if not clean_docs:
        print("No documents were processed. Check input directory and extensions.")
        return

    dataset_summary = summarize_dataset(clean_docs)
    results = {}
    retrieval_results: dict[str, dict] = {}
    for strategy in ("paragraph", "sentence_window"):
        chunks = chunk_documents(clean_docs, strategy=strategy)
        results[strategy] = summarize(chunks)
        probe = run_retrieval_probe(chunks, args.query_file)
        if probe is not None:
            retrieval_results[strategy] = probe

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = render_markdown(results, dataset_summary, retrieval_results or None)
    (output_dir / "chunking_comparison.md").write_text(output, encoding="utf-8")
    
    print("\n" + output)
    print(f"\nReport saved to: {output_dir / 'chunking_comparison.md'}")


if __name__ == "__main__":
    main()
