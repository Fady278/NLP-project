from retrieval.models.embedding_model import EmbeddingModel

class IndexingService:
    def __init__(self, vectordb_client):
        self.embedding_client = EmbeddingModel()
        self.vectordb_client = vectordb_client

    def push_data_to_index(self, project, chunks, do_reset=0):
        collection_name = self.vectordb_client.create_collection_name(project.id)
        
        if do_reset:
         self.vectordb_client.delete_collection(collection_name) 

        text = [c.text for c in chunks]
        metadata = [c.metadata for c in chunks]

        vectors = [
            self.embedding_client.embed(text=t, doc_type="passage")
            for t in text
        ]

        self.vectordb_client.create_collection(
            collection_name,
            self.embedding_client.embedding_size
        )

        self.vectordb_client.add_documents(
            collection_name=collection_name,
            texts=text,
            vectors=vectors,
            metadata=metadata
        )
        