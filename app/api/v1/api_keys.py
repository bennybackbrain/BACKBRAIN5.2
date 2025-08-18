from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user, get_session_dep
from app.core.api_keys import create_api_key, revoke_api_key
from app.database.models import APIKeyORM

router = APIRouter(prefix="/keys", tags=["api-keys"])

class APIKeyOut(BaseModel):
    id: int
    name: str
    created_at: str
    last_used_at: str | None

class APIKeyCreateOut(BaseModel):
    name: str
    key: str

@router.post("/", response_model=APIKeyCreateOut)
async def create_key(name: str, session: Session = Depends(get_session_dep), user=Depends(get_current_user)):
    raw = create_api_key(session, name)
    return {"name": name, "key": raw}

@router.get("/", response_model=list[APIKeyOut])
async def list_keys(session: Session = Depends(get_session_dep), user=Depends(get_current_user)):
    keys = session.query(APIKeyORM).all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "created_at": k.created_at.isoformat(),
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in keys
    ]


@router.delete("/{key_id}", status_code=204)
async def revoke(key_id: int, session: Session = Depends(get_session_dep), user=Depends(get_current_user)):
    ok = revoke_api_key(session, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": {"code": "KEY_NOT_FOUND", "message": "Key not found or already revoked"}})
    return None
