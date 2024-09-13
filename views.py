from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer

from .crud import get_service

streamalerts_generic_router = APIRouter()


def streamalerts_renderer():
    return template_renderer(["streamalerts/templates"])


@streamalerts_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    """Return the extension's settings page"""
    return streamalerts_renderer().TemplateResponse(
        "streamalerts/index.html", {"request": request, "user": user.dict()}
    )


@streamalerts_generic_router.get("/{state}")
async def donation(state, request: Request):
    """Return the donation form for the Service corresponding to state"""
    service = await get_service(by_state=state)
    if not service:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Service does not exist."
        )
    return streamalerts_renderer().TemplateResponse(
        "streamalerts/display.html",
        {"request": request, "twitchuser": service.twitchuser, "service": service.id},
    )
