from fastapi import APIRouter

from .crud import db
from .views import streamalerts_generic_router
from .views_api import streamalerts_api_router

streamalerts_ext: APIRouter = APIRouter(prefix="/streamalerts", tags=["streamalerts"])
streamalerts_ext.include_router(streamalerts_generic_router)
streamalerts_ext.include_router(streamalerts_api_router)

streamalerts_static_files = [
    {
        "path": "/streamalerts/static",
        "name": "streamalerts_static",
    }
]

__all__ = ["db", "streamalerts_ext", "streamalerts_static_files"]
