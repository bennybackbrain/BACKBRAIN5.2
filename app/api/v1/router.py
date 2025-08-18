from fastapi import APIRouter

from . import endpoints
from . import jobs
from . import auth
from . import webdav
from . import api_keys
from . import ingest

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(endpoints.router, tags=["entries"])
api_router.include_router(jobs.router)
api_router.include_router(webdav.router)
api_router.include_router(api_keys.router)
api_router.include_router(ingest.router)
from app.api.v1 import query as query_router
api_router.include_router(query_router.router)
