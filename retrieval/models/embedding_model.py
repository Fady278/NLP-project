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

    @property
    def embedding_size(self) -> int:
        return self.model.get_sentence_embedding_dimension()
    
    