from __future__ import annotations

import sys
from typing import Any

from api.services.errors import ApiServiceError
from api.services.llm_base import BaseLLMService
from api.services.query_service import QueryApplicationService


PROBES: list[dict[str, Any]] = [
    {
        "id": "multi-chunk-graduation",
        "query": "ما شروط التخرج من حيث عدد الساعات والمعدل التراكمي والتدريب الصيفي؟",
        "top_k": 5,
    },
    {
        "id": "out-of-scope-housing",
        "query": "ما رسوم السكن الجامعي لطلاب الكلية؟",
        "top_k": 5,
    },
]


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


def run_probe(service: QueryApplicationService, probe: dict[str, Any]) -> tuple[Any, str]:
    try:
        response = service.execute(
            project_id="demo-project",
            query=probe["query"],
            top_k=probe["top_k"],
            prompt_version="strict",
        )
        return response, "live-llm"
    except ApiServiceError:
        fallback_service = QueryApplicationService(
            processed_dir="data/processed",
            llm_service=RetrievalOnlyLLM(),
        )
        response = fallback_service.execute(
            project_id="demo-project",
            query=probe["query"],
            top_k=probe["top_k"],
            prompt_version="strict",
        )
        return response, "retrieval-only-fallback"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    service = QueryApplicationService(processed_dir="data/processed")

    for probe in PROBES:
        response, mode = run_probe(service, probe)
        chunks = response.retrieved_context or []
        pages = [
            str((chunk.metadata or {}).get("page_label") or (chunk.metadata or {}).get("page_num") or "?")
            for chunk in chunks
        ]
        print(f"=== {probe['id']} ===")
        print(f"mode: {mode}")
        print(f"query: {probe['query']}")
        print(f"answer: {response.answer}")
        print(f"retrieved_count: {len(chunks)}")
        print(f"pages: {pages}")
        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.metadata or {}
            source_name = metadata.get("source_name") or metadata.get("source_path") or "unknown"
            preview = " ".join((chunk.text or "").split())[:220]
            print(f"chunk_{index}: page={metadata.get('page_label') or metadata.get('page_num') or '?'} source={source_name}")
            print(f"preview_{index}: {preview}")
        print()


if __name__ == "__main__":
    main()
