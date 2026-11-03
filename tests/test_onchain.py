from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from lnbits.core.models import KeyType, User, Wallet, WalletTypeInfo

from .. import crud, views_api
from ..models import ChargeStatus, CreateService, Service

TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def merchant(monkeypatch):
    wallet = Wallet(
        id="merchant",
        name="Donations",
        user="owner",
        adminkey="admin",
        inkey="invoice",
        created_at=TIME,
        updated_at=TIME,
    )
    chain = wallet.model_copy(
        update={"id": "chain", "wallet_type": "onchain", "onchain_network": "Testnet4"}
    )
    user = User(id="owner", wallets=[wallet, chain], created_at=TIME, updated_at=TIME)
    monkeypatch.setattr(views_api, "get_user", AsyncMock(return_value=user))
    monkeypatch.setattr(views_api, "get_wallet", AsyncMock(return_value=wallet))
    return WalletTypeInfo(KeyType.admin, wallet)


@pytest.fixture
def service(monkeypatch):
    service = Service(
        id="service",
        state="public-link",
        twitchuser="streamer",
        client_id="client",
        client_secret="secret",
        wallet="merchant",
        servicename="Streamlabs",
        authenticated=True,
        token="token",
        onchain="watchonly-id",
    )
    monkeypatch.setattr(views_api, "get_service", AsyncMock(return_value=service))
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize("edit", [False, True])
@pytest.mark.parametrize(
    "wallet, reference, status",
    [
        ("merchant", "core:chain", 400),
        ("merchant", "core:foreign", 403),
        ("foreign", "core:chain", 403),
    ],
)
async def test_invalid_wallet_cannot_be_saved(
    monkeypatch, merchant, service, edit, wallet, reference, status
):
    monkeypatch.setattr(
        views_api, "get_satspay_network", AsyncMock(return_value="Mainnet")
    )
    save = AsyncMock()
    monkeypatch.setattr(views_api, "create_service", save)
    monkeypatch.setattr(views_api, "update_service", save)
    data = CreateService.model_validate(
        {**service.model_dump(), "wallet": wallet, "onchain": reference}
    )
    with pytest.raises(HTTPException) as exc:
        if edit:
            await views_api.api_update_service(service.id, data, merchant)
        else:
            await views_api.api_create_service(data, merchant)
    assert exc.value.status_code == status
    assert service.onchain == "watchonly-id"
    save.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reference, method",
    [("core:chain", "GET"), ("watchonly-id", "POST"), (None, "POST")],
)
async def test_donation_checkout_and_paid_alert(
    monkeypatch, merchant, service, reference, method
):
    service.onchain = reference
    monkeypatch.setattr(
        views_api, "get_satspay_network", AsyncMock(return_value="Testnet4")
    )
    save_service = AsyncMock(side_effect=lambda updated: updated)
    monkeypatch.setattr(views_api, "update_service", save_service)
    if reference == "core:chain":
        service.onchain = "watchonly-id"
        data = CreateService.model_validate(
            {**service.model_dump(), "onchain": reference}
        )
        await views_api.api_update_service(service.id, data, merchant)
        assert (service.state, service.token, service.authenticated) == (
            "public-link",
            "token",
            True,
        )

    app = FastAPI()
    app.include_router(views_api.streamalerts_api_router, prefix="/streamalerts")
    create_charge = AsyncMock(return_value="charge")
    create_donation = AsyncMock()
    monkeypatch.setattr(views_api, "btc_price", AsyncMock(return_value=100_000))
    monkeypatch.setattr(views_api, "create_charge", create_charge)
    monkeypatch.setattr(views_api, "create_donation", create_donation)
    monkeypatch.setattr(
        views_api,
        "get_donation",
        AsyncMock(return_value=SimpleNamespace(id="charge", wallet="merchant")),
    )
    get_status = AsyncMock(
        side_effect=[
            ChargeStatus(id="charge", paid=False),
            ChargeStatus(id="charge", paid=True),
        ]
    )
    post = AsyncMock(return_value={"sent": True})
    monkeypatch.setattr(views_api, "get_charge_status", get_status)
    monkeypatch.setattr(views_api, "post_donation", post)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        checkout = await client.post(
            "/streamalerts/api/v1/donations",
            json={"service": service.id, "sats": 1000},
        )
        assert checkout.json() == {"redirect_url": "/satspay/charge"}
        webhook = "/streamalerts/api/v1/postdonation"
        # SatsPay sends a JSON body without a content type on GET.
        payload = '{"id":"charge","paid":true}'
        assert (
            await client.request(method, webhook, content=payload)
        ).status_code == 400
        post.assert_not_awaited()
        paid = await client.request(method, webhook, content=payload)
        assert paid.json() == {"sent": True}
        assert paid.headers["Cache-Control"] == "no-store"

    assert create_charge.await_args is not None
    assert create_charge.await_args.kwargs["data"]["onchainwallet"] == reference
    assert create_charge.await_args.kwargs["api_key"] == "invoice"
    assert create_donation.await_args is not None
    assert create_donation.await_args.kwargs["donation_id"] == "charge"
    get_status.assert_awaited_with("charge", "invoice")
    post.assert_awaited_once_with("charge")


@pytest.mark.asyncio
async def test_failed_streamlabs_delivery_leaves_donation_unposted(
    monkeypatch, service
):

    donation = SimpleNamespace(
        posted=False,
        service=service.id,
        name="Donor",
        message="",
        amount=1,
        cur_code="USD",
    )
    monkeypatch.setattr(crud, "get_donation", AsyncMock(return_value=donation))
    monkeypatch.setattr(crud, "get_service", AsyncMock(return_value=service))
    save = AsyncMock()
    monkeypatch.setattr(crud.db, "execute", save)
    client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    monkeypatch.setattr(crud.httpx, "AsyncClient", lambda: client(transport=transport))

    with pytest.raises(httpx.HTTPStatusError):
        await crud.post_donation("charge")
    save.assert_not_awaited()
