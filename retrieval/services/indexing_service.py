from retrieval.models.embedding_model import EmbeddingModel

class IndexingService:
    def __init__(self, vectordb_client):
        self.embedding_client = EmbeddingModel()
        self.vectordb_client = vectordb_client

    def push_data_to_index(self, project, chunks, do_reset: bool = False):
        collection_name = self.vectordb_client.create_collection_name(project.id)
        
        if do_reset:
            self.vectordb_client.delete_collection(collection_name) 

        text = [c.text for c in chunks]
        metadata = [
            {
                **c.metadata,
                "chunk_id": c.chunk_id,
                "source_doc_id": c.source_doc_id,
                "source_path": c.source_path,
                "file_type": c.file_type,
                "page_num": c.page_num,
                "strategy": c.strategy,
            }
            for c in chunks
        ]
        point_ids = [c.chunk_id for c in chunks]

        vectors = self.embedding_client.embed_batch(text, doc_type="passage")

        self.vectordb_client.create_collection(
            collection_name,
            self.embedding_client.embedding_size
        )

        self.vectordb_client.add_documents(
            collection_name=collection_name,
            texts=text,
            vectors=vectors,
            metadata=metadata,
            point_ids=point_ids
        )
        
