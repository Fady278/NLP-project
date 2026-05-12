from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

from api.services.errors import ApiServiceError, DependencyConfigurationError
from api.services.query_service import QueryApplicationService
from api.services.llm_base import BaseLLMService


@dataclass
class EvalCase:
    id: str
    query: str
    expected_source_contains: list[str] = field(default_factory=list)
    expected_chunk_contains: list[str] = field(default_factory=list)
    expected_answer_keywords: list[str] = field(default_factory=list)
    forbidden_source_contains: list[str] = field(default_factory=list)
    notes: str = ""
    top_k: int = 5
    prompt_version: str = "strict"

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "EvalCase":
        return cls(
            id=str(raw.get("id") or f"case-{index+1}"),
            query=str(raw["query"]),
            expected_source_contains=[str(item) for item in raw.get("expected_source_contains", [])],
            expected_chunk_contains=[str(item) for item in raw.get("expected_chunk_contains", [])],
            expected_answer_keywords=[str(item) for item in raw.get("expected_answer_keywords", [])],
            forbidden_source_contains=[str(item) for item in raw.get("forbidden_source_contains", [])],
            notes=str(raw.get("notes") or ""),
            top_k=int(raw.get("top_k") or 5),
            prompt_version=str(raw.get("prompt_version") or "strict"),
        )


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def answer_is_idk(answer: str) -> bool:
    normalized = normalize_text(answer).rstrip(".")
    return normalized == "i don't know"


def source_matches(source_path: str, needles: list[str]) -> bool:
    haystack = normalize_text(source_path)
    return any(normalize_text(needle) in haystack for needle in needles)


def keyword_match(answer: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = normalize_text(answer)
    return all(normalize_text(keyword) in haystack for keyword in keywords)


def chunk_match(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = normalize_text(text)
    return all(normalize_text(keyword) in haystack for keyword in keywords)


def classify_failure(
    *,
    retrieval_hit: bool,
    forbidden_hit: bool,
    answer: str,
    answer_keywords_ok: bool,
    retrieved_count: int,
) -> str | None:
    if forbidden_hit:
        return "cross-document pollution"
    if retrieved_count == 0:
        return "empty retrieval"
    if not retrieval_hit:
        return "wrong chunk retrieved"
    if answer_is_idk(answer):
        return "relevant context found but answer abstained"
    if not answer_keywords_ok:
        return "answer missed expected facts"
    return None


def run_case(
    service: QueryApplicationService,
    *,
    project_id: str,
    case: EvalCase,
) -> dict[str, Any]:
    response = service.execute(
        project_id=project_id,
        query=case.query,
        top_k=case.top_k,
        prompt_version=case.prompt_version,
    )
    chunks = response.retrieved_context or []
    chunk_texts = [
        str(getattr(chunk, "text", ""))
        for chunk in chunks
    ]
    source_paths = [
        str(getattr(chunk, "metadata", {}).get("source_path", ""))
        for chunk in chunks
    ]
    retrieval_hit = any(source_matches(path, case.expected_source_contains) for path in source_paths) if case.expected_source_contains else True
    evidence_hit = any(chunk_match(text, case.expected_chunk_contains) for text in chunk_texts)
    forbidden_hit = any(source_matches(path, case.forbidden_source_contains) for path in source_paths) if case.forbidden_source_contains else False
    answer_keywords_ok = keyword_match(response.answer, case.expected_answer_keywords)
    failure_reason = classify_failure(
        retrieval_hit=retrieval_hit and evidence_hit,
        forbidden_hit=forbidden_hit,
        answer=response.answer,
        answer_keywords_ok=answer_keywords_ok,
        retrieved_count=len(chunks),
    )

    return {
        "id": case.id,
        "query": case.query,
        "notes": case.notes,
        "retrieved_count": len(chunks),
        "top_source": source_paths[0] if source_paths else "",
        "sources": source_paths,
        "answer": response.answer,
        "retrieval_hit": retrieval_hit,
        "evidence_hit": evidence_hit,
        "forbidden_hit": forbidden_hit,
        "answer_keywords_ok": answer_keywords_ok,
        "passed": failure_reason is None,
        "failure_reason": failure_reason,
    }


def load_cases(path: Path) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Evaluation cases file must be a JSON array.")
    return [EvalCase.from_dict(item, index) for index, item in enumerate(raw)]


def build_markdown_report(project_id: str, results: list[dict[str, Any]]) -> str:
    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    retrieval_hits = sum(1 for item in results if item["retrieval_hit"])
    evidence_hits = sum(1 for item in results if item.get("evidence_hit"))
    lines = [
        "# Phase 4: Retrieval Evaluation & Error Analysis",
        "",
        f"- Project ID: `{project_id}`",
        f"- Cases run: **{total}**",
        f"- Retrieval hit rate: **{retrieval_hits}/{total}**",
        f"- Evidence-backed hit rate: **{evidence_hits}/{total}**",
        f"- Full-pass rate: **{passed}/{total}**",
        "",
        "## Case Summary",
        "",
        "| Case | Retrieval | Evidence | Answer | Status | Failure Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        retrieval = "hit" if item["retrieval_hit"] else "miss"
        evidence = "hit" if item.get("evidence_hit") else "miss"
        answer = "IDK" if answer_is_idk(item["answer"]) else "generated"
        status = "pass" if item["passed"] else "fail"
        lines.append(
            f"| `{item['id']}` | {retrieval} | {evidence} | {answer} | {status} | {item['failure_reason'] or '-'} |"
        )

    failing = [item for item in results if not item["passed"]]
    lines.extend(["", "## Edge Cases", ""])
    if not failing:
        lines.append("No failing edge cases were detected in this run.")
        return "\n".join(lines)

    for item in failing:
        lines.extend(
            [
                f"### {item['id']}",
                f"- Query: `{item['query']}`",
                f"- Failure type: **{item['failure_reason']}**",
                f"- Retrieved count: {item['retrieved_count']}",
                f"- Top source: `{item['top_source'] or 'none'}`",
                f"- Evidence hit: {'yes' if item.get('evidence_hit') else 'no'}",
                f"- Notes: {item['notes'] or 'n/a'}",
                f"- Answer excerpt: `{item['answer'][:240]}`",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 4 RAG evaluation cases and generate a markdown report.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--cases", default="docs/evaluation_cases.sample.json")
    parser.add_argument("--output", default="docs/phase4_evaluation_report.md")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument("--retrieval-only", action="store_true")
    return parser.parse_args()


class RetrievalOnlyLLM(BaseLLMService):
    @property
    def provider_name(self) -> str:
        return "retrieval-only"

    @property
    def model(self) -> str:
        return "none"

    def generate(self, prompt: str) -> str:
        return "I don't know."

    def metadata(self) -> dict[str, Any]:
        return {"provider": self.provider_name, "model": self.model}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    cases = load_cases(Path(args.cases))
    llm_service: BaseLLMService | None = RetrievalOnlyLLM() if args.retrieval_only else None
    try:
        service = QueryApplicationService(processed_dir=args.processed_dir, llm_service=llm_service)
    except DependencyConfigurationError:
        service = QueryApplicationService(processed_dir=args.processed_dir, llm_service=RetrievalOnlyLLM())
    results: list[dict[str, Any]] = []

    for case in cases:
        try:
            results.append(run_case(service, project_id=args.project_id, case=case))
        except ApiServiceError as exc:
            results.append(
                {
                    "id": case.id,
                    "query": case.query,
                    "notes": case.notes,
                    "retrieved_count": 0,
                    "top_source": "",
                    "sources": [],
                    "answer": exc.details or exc.message,
                    "retrieval_hit": False,
                    "evidence_hit": False,
                    "forbidden_hit": False,
                    "answer_keywords_ok": False,
                    "passed": False,
                    "failure_reason": "pipeline error",
                }
            )

    report = build_markdown_report(args.project_id, results)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
