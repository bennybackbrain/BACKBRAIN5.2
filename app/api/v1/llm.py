from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List
from app.core.security import get_current_user
from app.services import llm

router = APIRouter(prefix="/llm", tags=["llm"])

class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|system|assistant)$")
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str | None = None

class ChatResponse(BaseModel):
    model: str
    content: str

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user=Depends(get_current_user)):
    result = llm.chat([m.model_dump() for m in req.messages], model=req.model)
    return ChatResponse(**result)
