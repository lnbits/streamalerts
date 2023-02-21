import httpx

from lnbits.app import settings

from .models import ChargeStatus


async def create_charge(data: dict, api_key: str) -> str:
    async with httpx.AsyncClient() as client:
        headers = {"X-API-KEY": api_key}
        r = await client.post(
            url=f"http://{settings.host}:{settings.port}/satspay/api/v1/charge",
            headers=headers,
            json=data,
        )
        r.raise_for_status()
        return r.json()["id"]


async def get_charge_status(charge_id: str, api_key: str) -> ChargeStatus:
    async with httpx.AsyncClient() as client:
        headers = {"X-API-KEY": api_key}
        r = await client.get(
            url=f"http://{settings.host}:{settings.port}/satspay/api/v1/charge/{charge_id}",
            headers=headers,
        )
        r.raise_for_status()
        return ChargeStatus.parse_obj(r.json())

async def delete_charge(charge_id: str, api_key: str):
    async with httpx.AsyncClient() as client:
        headers = {"X-API-KEY": api_key}
        r = await client.delete(
            url=f"http://{settings.host}:{settings.port}/satspay/api/v1/charge/{charge_id}",
            headers=headers,
        )
        r.raise_for_status()