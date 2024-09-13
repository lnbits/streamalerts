from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.models import WalletTypeInfo
from lnbits.decorators import require_admin_key, require_invoice_key
from lnbits.utils.exchange_rates import btc_price

from .crud import (
    authenticate_service,
    create_donation,
    create_service,
    delete_donation,
    delete_service,
    get_donation,
    get_donations,
    get_service,
    get_service_redirect_uri,
    get_services,
    post_donation,
    update_donation,
    update_service,
)
from .helpers import create_charge, delete_charge, get_charge_status
from .models import CreateDonation, CreateService, Donation, Service, ValidateDonation

streamalerts_api_router = APIRouter()


@streamalerts_api_router.post(
    "/api/v1/services", dependencies=[Depends(require_admin_key)]
)
async def api_create_service(data: CreateService) -> Service:
    """Create a service, which holds data about how/where to post donations"""
    try:
        service = await create_service(data=data)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return service


@streamalerts_api_router.get("/api/v1/getaccess/{service_id}")
async def api_get_access(service_id, request: Request):
    """Redirect to Streamlabs' Approve/Decline page for API access for Service
    with service_id
    """
    service = await get_service(service_id)
    if service:
        redirect_uri = await get_service_redirect_uri(request, service_id)
        params = {
            "response_type": "code",
            "client_id": service.client_id,
            "redirect_uri": redirect_uri,
            "scope": "donations.create",
            "state": service.state,
        }
        endpoint_url = "https://streamlabs.com/api/v1.0/authorize/?"
        querystring = "&".join([f"{key}={value}" for key, value in params.items()])
        redirect_url = endpoint_url + querystring
        return RedirectResponse(redirect_url)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Service does not exist!"
        )


@streamalerts_api_router.get("/api/v1/authenticate/{service_id}")
async def api_authenticate_service(
    service_id, request: Request, code: str = Query(...), state: str = Query(...)
):
    """Endpoint visited via redirect during third party API authentication

    If successful, an API access token will be added to the service, and
    the user will be redirected to index.html.
    """

    service = await get_service(service_id)
    assert service

    if service.state != state:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="State doesn't match!"
        )

    redirect_uri = request.url.scheme + "://" + request.headers["Host"]
    redirect_uri += f"/streamalerts/api/v1/authenticate/{service_id}"
    url, success = await authenticate_service(service_id, code, redirect_uri)
    if success:
        return RedirectResponse(url)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Service already authenticated!"
        )


@streamalerts_api_router.post("/api/v1/donations")
async def api_create_donation(data: CreateDonation, request: Request):
    """Take data from donation form and return satspay charge"""
    # Currency is hardcoded while frotnend is limited
    # Fiat amount is calculated here while frontend is limited
    price = await btc_price(data.cur_code)
    amount = data.sats * (10 ** (-8)) * price
    webhook_base = request.url.scheme + "://" + request.headers["Host"]
    service = await get_service(data.service)
    if not service:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Service not found!"
        )
    wallet = await get_wallet(service.wallet)
    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found!"
        )
    description = f"{data.sats} sats donation from {data.name} to {service.twitchuser}"
    create_charge_data = {
        "amount": data.sats,
        "completelink": f"https://twitch.tv/{service.twitchuser}",
        "completelinktext": "Back to Stream!",
        "webhook": webhook_base + "/streamalerts/api/v1/postdonation",
        "description": description,
        "time": 1440,
        "lnbitswallet": service.wallet,
        "onchainwallet": service.onchain,
        "user": wallet.user,
    }
    assert wallet, f"Could not fetch wallet: {service.wallet}"
    charge_id = await create_charge(data=create_charge_data, api_key=wallet.inkey)
    await create_donation(
        data=data,
        donation_id=charge_id,
        amount=amount,
    )
    return {"redirect_url": f"/satspay/{charge_id}"}


@streamalerts_api_router.post("/api/v1/postdonation")
async def api_post_donation(data: ValidateDonation):
    """Post a paid donation to Stremalabs/StreamElements.
    This endpoint acts as a webhook for the SatsPayServer extension."""

    donation_id = data.id
    donation = await get_donation(donation_id)
    if not donation:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Donation '{donation_id}' not found!",
        )
    wallet = await get_wallet(donation.wallet)
    assert wallet, f"Could not fetch wallet: {donation.wallet}"

    charge = await get_charge_status(donation_id, wallet.inkey)
    if charge and charge.paid:
        return await post_donation(donation_id)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Not a paid charge!"
        )


@streamalerts_api_router.get("/api/v1/services")
async def api_get_services(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> list[Service]:
    """Return list of all services assigned to wallet with given invoice key"""
    user = await get_user(key_info.wallet.user)
    wallet_ids = user.wallet_ids if user else []
    services = []
    for wallet_id in wallet_ids:
        new_services = await get_services(wallet_id)
        services += new_services if new_services else []
    return services


@streamalerts_api_router.get("/api/v1/donations")
async def api_get_donations(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> list[Donation]:
    """Return list of all donations assigned to wallet with given invoice
    key
    """
    user = await get_user(key_info.wallet.user)
    wallet_ids = user.wallet_ids if user else []
    donations = []
    for wallet_id in wallet_ids:
        new_donations = await get_donations(wallet_id)
        donations += new_donations if new_donations else []
    return donations


@streamalerts_api_router.put("/api/v1/donations/{donation_id}")
async def api_update_donation(
    data: CreateDonation,
    donation_id: str,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Donation:
    """Update a donation with the data given in the request"""
    donation = await get_donation(donation_id)

    if not donation:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Donation does not exist."
        )

    if donation.wallet != key_info.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your donation."
        )

    for k, v in data.dict().items():
        setattr(donation, k, v)
    await update_donation(donation)
    return donation


@streamalerts_api_router.put("/api/v1/services/{service_id}")
async def api_update_service(
    service_id: str,
    data: CreateService,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Service:
    """Update a service with the data given in the request"""
    service = await get_service(service_id)

    if not service:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Service does not exist."
        )

    if service.wallet != key_info.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your service."
        )

    for k, v in data.dict().items():
        setattr(service, k, v)

    service = await update_service(service)
    return service


@streamalerts_api_router.delete("/api/v1/donations/{donation_id}")
async def api_delete_donation(
    donation_id: str, key_info: WalletTypeInfo = Depends(require_admin_key)
):
    """Delete the donation with the given donation_id"""
    donation = await get_donation(donation_id)
    if not donation:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No donation with this ID!"
        )
    if donation.wallet != key_info.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this donation!",
        )
    await delete_donation(donation_id)
    await delete_charge(donation_id, key_info.wallet.adminkey)
    return "", HTTPStatus.NO_CONTENT


@streamalerts_api_router.delete("/api/v1/services/{service_id}")
async def api_delete_service(
    service_id: str, key_info: WalletTypeInfo = Depends(require_admin_key)
):
    """Delete the service with the given service_id"""
    service = await get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No service with this ID!"
        )
    if service.wallet != key_info.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this service!",
        )
    donations = await delete_service(service_id)
    for d in donations:
        await delete_charge(d, key_info.wallet.adminkey)
