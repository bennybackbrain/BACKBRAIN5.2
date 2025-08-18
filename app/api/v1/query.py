from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
import os, time
from fastapi import Request, Header, HTTPException, status, Depends
from app.core.config import settings
from app.services.llm import call_llm  # vorhandener LLM-Wrapper
from app.api.v1.models_query import QueryRequest, QueryResponse
from app.services.summary_loader import iter_cached_summaries
from app.services.query_helpers import rank_by_query_heuristic
router = APIRouter(tags=["query"])

def check_api_key(x_api_key: str = Header(...)):
    # Minimaler Check, kann erweitert werden
    if not x_api_key or x_api_key == "":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    return x_api_key

@router.post("/query", response_model=QueryResponse, dependencies=[Depends(check_api_key)])
def query_endpoint(body: QueryRequest) -> QueryResponse:
    t0 = time.time()
    limit_files = int(os.getenv("QUERY_MAX_SUMMARIES", "500"))
    texts = list(iter_cached_summaries(limit_files=limit_files))
    if not texts:
        return QueryResponse(answer="Keine Summaries im Cache verfügbar.", sources=[], used={"count_considered": 0, "count_used": 0})
    top_k = body.top_k or int(os.getenv("QUERY_TOPK_DEFAULT", "50"))
    ranked = rank_by_query_heuristic(body.query, texts)[:top_k]
    system = "Beantworte prägnant nur auf Basis der bereitgestellten Summaries. Zitiere kurz Quellen (Dateinamen)."
    def short(snippet: str, max_chars: int = 1500) -> str:
        return snippet[:max_chars]
    context_parts = [f"# {fname}\n{short(content)}" for fname, content in ranked]
    user = f"FRAGE: {body.query}\n\nKONTEXT:\n" + "\n\n".join(context_parts)
    answer = call_llm(system=system, user=user, model=settings.summary_model, max_tokens=body.max_tokens or 800)
    sources = [fname for fname, _ in ranked]
    return QueryResponse(answer=answer, sources=sources if (body.return_sources or True) else [], used={"count_considered": len(texts), "count_used": len(ranked)})
