from fastapi import APIRouter

from . import endpoints
from . import jobs
from . import auth
from . import webdav

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(endpoints.router, tags=["entries"])
api_router.include_router(jobs.router)
api_router.include_router(webdav.router)
