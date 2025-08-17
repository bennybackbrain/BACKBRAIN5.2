from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.security import authenticate_user, create_access_token, get_session_dep, hash_password
from app.core.config import settings
from app.database.models import UserORM

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    model_config = ConfigDict(json_schema_extra={"example": {"access_token": "<jwt>", "token_type": "bearer"}})

@router.post("/token", response_model=TokenOut, summary="Obtain access token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session_dep)):
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail={"error": {"code": "LOGIN_FAILED", "message": "Incorrect username or password"}})
    token = create_access_token(user.username)
    return {"access_token": token, "token_type": "bearer"}

async def ensure_bootstrap_user(session: Session = Depends(get_session_dep)):
    if settings.default_admin_username and settings.default_admin_password:
        exists = session.query(UserORM).filter(UserORM.username == settings.default_admin_username).first()
        if not exists:
            session.add(UserORM(username=settings.default_admin_username, hashed_password=hash_password(settings.default_admin_password)))
            session.commit()
