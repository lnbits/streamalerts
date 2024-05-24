from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_streamalerts")

streamalerts_ext: APIRouter = APIRouter(prefix="/streamalerts", tags=["streamalerts"])

streamalerts_static_files = [
    {
        "path": "/streamalerts/static",
        "name": "streamalerts_static",
    }
]


def streamalerts_renderer():
    return template_renderer(["streamalerts/templates"])


from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403
