from typing import Optional

import httpx
from lnbits.core.crud import get_wallet
from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import CreateDonation, CreateService, Donation, Service

db = Database("ext_streamalerts")


async def get_service_redirect_uri(request, service_id):
    """Return the service's redirect URI, to be given to the third party API"""
    uri_base = request.url.scheme + "://"
    uri_base += request.headers["Host"] + "/streamalerts/api/v1"
    redirect_uri = uri_base + f"/authenticate/{service_id}"
    return redirect_uri


async def create_donation(
    data: CreateDonation, wallet: str, amount: float, donation_id: Optional[str] = None
) -> Donation:
    """Create a new Donation"""
    donation = Donation(
        id=donation_id or urlsafe_short_hash(),
        amount=amount,
        wallet=wallet,
        **data.dict(),
    )
    await db.insert("streamalerts.donations", donation)
    return donation


async def post_donation(donation_id: str) -> dict:
    """Post donations to their respective third party APIs

    If the donation has already been posted, it will not be posted again.
    """
    donation = await get_donation(donation_id)
    if not donation:
        return {"message": "Donation not found!"}
    if donation.posted:
        return {"message": "Donation has already been posted!"}

    service = await get_service(donation.service)
    assert service, "Couldn't fetch service to donate to"

    if service.servicename == "Streamlabs":
        url = "https://streamlabs.com/api/v1.0/donations"
        data = {
            "name": donation.name[:25],
            "message": donation.message[:255],
            "identifier": "LNbits",
            "amount": donation.amount,
            "currency": donation.cur_code.upper(),
            "access_token": service.token,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
    elif service.servicename == "StreamElements":
        return {"message": "StreamElements not yet supported!"}
    else:
        return {"message": "Unsopported servicename"}
    await db.execute(
        "UPDATE streamalerts.donations SET posted = :posted WHERE id = :id",
        {"id": donation_id, "posted": True},
    )
    return response.json()


async def create_service(data: CreateService) -> Service:
    """Create a new Service"""
    service = Service(
        id=urlsafe_short_hash(),
        state=urlsafe_short_hash(),
        **data.dict(),
    )
    await db.insert("streamalerts.services", service)
    return service


async def get_service(
    service_id: Optional[str] = None, by_state: Optional[str] = None
) -> Optional[Service]:
    """Return a service either by ID or, available, by state

    Each Service's donation page is reached through its "state" hash
    instead of the ID, preventing accidental payments to the wrong
    streamer via typos like 2 -> 3.
    """
    assert service_id or by_state, "Must provide either service_id or by_state"
    if by_state:
        return await db.fetchone(
            "SELECT * FROM streamalerts.services WHERE state = :state",
            {"state": by_state},
            Service,
        )
    else:
        return await db.fetchone(
            "SELECT * FROM streamalerts.services WHERE id = :id",
            {"id": service_id},
            Service,
        )


async def get_services(wallet_id: str) -> list[Service]:
    """Return all services belonging assigned to the wallet_id"""
    return await db.fetchall(
        "SELECT * FROM streamalerts.services WHERE wallet = :wallet",
        {"wallet": wallet_id},
        Service,
    )


async def authenticate_service(service_id, code, redirect_uri):
    """Use authentication code from third party API to retreive access token"""
    # The API token is passed in the querystring as 'code'
    service = await get_service(service_id)
    assert service, f"Could not fetch service: {service_id}"
    wallet = await get_wallet(service.wallet)
    assert wallet, f"Could not fetch wallet: {service.wallet}"
    user = wallet.user
    url = "https://streamlabs.com/api/v1.0/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": service.client_id,
        "client_secret": service.client_secret,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient() as client:
        response = (await client.post(url, data=data)).json()
    token = response["access_token"]
    success = await service_add_token(service_id, token)
    return f"/streamalerts/?usr={user}", success


async def service_add_token(service_id, token):
    """Add access token to its corresponding Service

    This also sets authenticated = 1 to make sure the token
    is not overwritten.
    Tokens for Streamlabs never need to be refreshed.
    """
    service = await get_service(service_id)
    assert service, f"Could not fetch service: {service_id}"
    if service.authenticated:
        return False

    await db.execute(
        """
        UPDATE streamalerts.services
        SET authenticated = 1, token = :token WHERE id = :id
        """,
        {"id": service_id, "token": token},
    )
    return True


async def delete_service(service_id: str) -> list[str]:
    """Delete a Service and all corresponding donations"""
    donations = await db.fetchall(
        "SELECT * FROM streamalerts.donations WHERE service = :service",
        {"service": service_id},
        Donation,
    )
    donation_ids = []
    for donation in donations:
        donation_ids.append(donation.id)
        await delete_donation(donation.id)

    await db.execute(
        "DELETE FROM streamalerts.services WHERE id = :id", {"id": service_id}
    )

    return donation_ids


async def get_donation(donation_id: str) -> Optional[Donation]:
    """Return a Donation"""
    return await db.fetchone(
        "SELECT * FROM streamalerts.donations WHERE id = :id",
        {"id": donation_id},
        Donation,
    )


async def get_donations(wallet_id: str) -> list[Donation]:
    """Return all streamalerts.donations assigned to wallet_id"""
    return await db.fetchall(
        "SELECT * FROM streamalerts.donations WHERE wallet = :wallet",
        {"wallet": wallet_id},
        Donation,
    )


async def delete_donation(donation_id: str) -> None:
    """Delete a Donation and its corresponding statspay charge"""
    await db.execute(
        "DELETE FROM streamalerts.donations WHERE id = :id", {"id": donation_id}
    )


async def update_donation(donation: Donation) -> Donation:
    """Update a Donation"""
    await db.update("streamalerts.donations", donation)
    return donation


async def update_service(service: Service) -> Service:
    """Update a service"""
    await db.update("streamalerts.services", service)
    return service
