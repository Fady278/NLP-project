from __future__ import annotations

from fastapi import APIRouter, Depends

from api.schemas.query import QueryRequest, QueryResponse
from api.services.query_service import QueryApplicationService

router = APIRouter(tags=["query"])


def get_query_service() -> QueryApplicationService:
    return QueryApplicationService()


@router.post("/query", response_model=QueryResponse)
def query_endpoint(
    payload: QueryRequest,
    service: QueryApplicationService = Depends(get_query_service),
) -> QueryResponse:
    return service.execute(
        project_id=payload.project_id,
        query=payload.query,
        conversation_context=payload.conversation_context,
        top_k=payload.top_k,
        prompt_version=payload.prompt_version,
    )
