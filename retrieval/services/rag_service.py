class RAGService:
    def __init__(self, retrieval_service, llm):
        self.retrieval_service = retrieval_service
        self.llm = llm

  
    # MAIN PIPELINE
    def generate_answer(self, project_id: str, query: str, top_k: int = 5, prompt_version: str = "strict"):
        prompt_version = self._normalize_prompt_version(prompt_version)

        # 1. Retrieve chunks 
        chunks = self.retrieval_service.search(
            project_id=project_id,
            query=query,
            top_k=top_k
        )

        if not chunks:
            return {
                "answer": "I don't know",
                "sources": [],
                "prompt_version": prompt_version
            }

        # 2. Build context
        context = self._build_context(chunks)

        # 3. Choose prompt version (A/B test)
        prompt = self._build_prompt(query, context, version=prompt_version)

        # 4. Call LLM
        try:
            answer = self.llm.generate(prompt)
        except Exception:
            return {
                "answer": "I don't know",
                "sources": self._extract_sources(chunks),
                "prompt_version": prompt_version
            }

        # 5. Return result
        return {
            "answer": answer,
            "sources": self._extract_sources(chunks),
            "prompt_version": prompt_version
        }


    # CONTEXT BUILDER
    def _build_context(self, chunks):
        context_parts = []

        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            source = metadata.get("source_doc_id", "unknown")

            context_parts.append(
                f"[{i+1}] {text} (source: {source})"
            )

        return "\n".join(context_parts)

    # PROMPT ENGINEERING (A/B TEST)
    def _build_prompt(self, query, context, version="strict"):
        if version == "simple":
            return f"""
Answer the question using the context.

Context:
{context}

Question:
{query}

Answer:
"""

        return f"""
You are a strict RAG assistant.

Rules:
- Use ONLY the provided context.
- If the answer is not in the context, say "I don't know".
- Do NOT guess or add external knowledge.

Context:
{context}

Question:
{query}

Answer:
"""

    def _normalize_prompt_version(self, version: str) -> str:
        normalized = (version or "strict").strip().lower()
        if normalized not in {"simple", "strict"}:
            raise ValueError("prompt_version must be either 'simple' or 'strict'")
        return normalized
  
    # SOURCES EXTRACTION
    def _extract_sources(self, chunks):
        sources = []
        seen = set()

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            source = {
                "source_doc_id": metadata.get("source_doc_id", "unknown"),
                "source_path": metadata.get("source_path", "unknown"),
                "page_num": metadata.get("page_num"),
            }
            source_key = (
                source["source_doc_id"],
                source["source_path"],
                source["page_num"],
            )
            if source_key in seen:
                continue
            seen.add(source_key)
            sources.append(source)

        return sources
