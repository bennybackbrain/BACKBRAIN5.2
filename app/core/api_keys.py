from __future__ import annotations
import secrets
import hashlib
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from app.database.models import APIKeyORM
from fastapi import Header, HTTPException, Depends
from app.core.security import get_session_dep

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def create_api_key(session: Session, name: str) -> str:
    raw = secrets.token_urlsafe(32)
    key_hash = _hash_key(raw)
    session.add(APIKeyORM(name=name, key_hash=key_hash))
    session.commit()
    return raw

def verify_api_key(session: Session, raw: str) -> APIKeyORM | None:
    key_hash = _hash_key(raw)
    key = session.query(APIKeyORM).filter(APIKeyORM.key_hash == key_hash, APIKeyORM.revoked_at.is_(None)).first()
    if key:
        key.last_used_at = datetime.now(UTC)
        session.commit()
    return key


async def api_key_dep(x_api_key: str | None = Header(None), session: Session = Depends(get_session_dep)) -> APIKeyORM:
    if not x_api_key:
        raise HTTPException(status_code=401, detail={"error": {"code": "API_KEY_REQUIRED", "message": "Missing X-API-Key"}})
    key = verify_api_key(session, x_api_key)
    if not key:
        raise HTTPException(status_code=401, detail={"error": {"code": "API_KEY_INVALID", "message": "Invalid or revoked API key"}})
    return key

def revoke_api_key(session: Session, key_id: int) -> bool:
    key = session.query(APIKeyORM).filter(APIKeyORM.id == key_id, APIKeyORM.revoked_at.is_(None)).first()
    if not key:
        return False
    key.revoked_at = datetime.now(UTC)
    session.commit()
    return True

__all__ = ["create_api_key", "verify_api_key", "api_key_dep", "revoke_api_key"]
