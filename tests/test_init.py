import pytest
from fastapi import APIRouter

from .. import streamalerts_ext


# just import router and add it to a test router
@pytest.mark.asyncio
async def test_router():
    router = APIRouter()
    router.include_router(streamalerts_ext)
