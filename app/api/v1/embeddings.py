from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_session_dep, get_current_user
from app.services.embeddings import embed_and_store, search_embeddings

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

class EmbedIn(BaseModel):
    content: str
    model: str | None = None

class EmbedOut(BaseModel):
    id: int
    model: str

@router.post("/", response_model=EmbedOut, summary="Create embedding for content")
async def create_embedding(body: EmbedIn, session: Session = Depends(get_session_dep), user=Depends(get_current_user)):
    if len(body.content) < 2:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONTENT_TOO_SHORT", "message": "Content too short"}})
    emb = embed_and_store(session, body.content, model=body.model or "pseudo-256")
    return {"id": emb.id, "model": emb.model}

from app.core.security import UserORM

@router.get("/search", summary="Embedding similarity search (cosine default)")
async def search(q: str = Query(..., min_length=2), limit: int = Query(5, ge=1, le=25), strategy: str = Query("cosine", pattern="^(cosine|l2)$"), session: Session = Depends(get_session_dep), user: UserORM = Depends(get_current_user)):
    results = search_embeddings(session, q, limit=limit, strategy=strategy)
    return [{"id": r.id, "model": r.model, "snippet": r.content[:200]} for r in results]
