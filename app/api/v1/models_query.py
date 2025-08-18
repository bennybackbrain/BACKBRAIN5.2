from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str
    top_k: int | None = 50
    max_tokens: int | None = 800
    return_sources: bool | None = True

class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []
    used: dict[str, int] = {}
