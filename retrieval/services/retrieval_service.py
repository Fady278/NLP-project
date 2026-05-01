from retrieval.models.embedding_model import EmbeddingModel

class RetrievalService:
    def __init__(self, vectordb_client):
        self.embedding_client = EmbeddingModel()
        self.vectordb_client = vectordb_client

    def search(self, project_id, query: str, top_k: int = 5, metadata_filter: dict | None = None):
    
        collection_name = self.vectordb_client.create_collection_name(project_id)

    
        query_vector = self.embedding_client.embed(text=query, doc_type="query")

    
        results = self.vectordb_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=top_k,
            metadata_filter=metadata_filter
        )

        return results
