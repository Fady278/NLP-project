from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

import uuid


class VectorDBClient:
    def __init__(self, host="localhost", port=6333):
        self.client = QdrantClient(host=host, port=port)

    def __init__(self):
        self.client = QdrantClient(
             url="https://85792c80-8c35-4758-ac29-1ee5ad050173.us-west-2-0.aws.cloud.qdrant.io:6333", 
            api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6M2E4ZDg4ZTktN2I4MC00ZTI4LWJkZjItODEwODVlMGVhNWI3In0.xN0neADOKMf9ik8o-HHJadJfAhL_Xk5N8u2qeJuKtV4",
        )

    # -------------------------
    # COLLECTION NAME
    # -------------------------
    def create_collection_name(self, project_id):
        return f"collection_{project_id}".strip()

    # -------------------------
    # CREATE COLLECTION
    # -------------------------
    def create_collection(self, name, dim):
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]

        if name not in existing:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE
                )
            )

    # -------------------------
    # ADD DOCUMENTS (INDEXING)
    # -------------------------
    def add_documents(self, collection_name, texts, vectors, metadata):

        points = []

        for text, vector, meta in zip(texts, vectors, metadata):

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "text": text,
                        "metadata": meta
                    }
                )
            )

        self.client.upsert(
            collection_name=collection_name,
            points=points
        )

    # -------------------------
    # SEARCH (IMPORTANT FOR RAG)
    # -------------------------
    def search(self, collection_name, query_vector, top_k=5):
     results = self.client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k
    ).points

     return [
        {
            "text": r.payload["text"],
            "metadata": r.payload["metadata"],
            "score": r.score
        }
        for r in results
    ]
    
    def delete_collection(self, name):
      collections = self.client.get_collections().collections
      existing = [c.name for c in collections]
      if name in existing:
        self.client.delete_collection(collection_name=name)