from sentence_transformers import SentenceTransformer

class EmbeddingModel:
    def __init__(self):
        # multilingual model (Arabic + English)
        self.model = SentenceTransformer("intfloat/multilingual-e5-base")

    def embed(self, text: str, doc_type: str = "passage") -> list[float]:
        # E5 models require prefix!
        if doc_type == "query":
            text = f"query: {text}"
        else:
            text = f"passage: {text}"

        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str], doc_type: str = "passage") -> list[list[float]]:
        prefixed_texts = []
        for text in texts:
            if doc_type == "query":
                prefixed_texts.append(f"query: {text}")
            else:
                prefixed_texts.append(f"passage: {text}")

        vectors = self.model.encode(prefixed_texts, normalize_embeddings=True)
        return vectors.tolist()

    @property
    def embedding_size(self) -> int:
        if hasattr(self.model, "get_embedding_dimension"):
            return self.model.get_embedding_dimension()
        return self.model.get_sentence_embedding_dimension()
    
    
