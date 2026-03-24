"""
FedEx REST API v1 client — OAuth2 client-credentials with auto-refresh.

Token is cached in-process with a 55-minute TTL (FedEx issues 3600s tokens).
All public methods are async-safe and handle token expiry transparently.
"""
import asyncio
import time
import logging
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Token cache — one shared state per process (Railway single-dyno is fine)
# ---------------------------------------------------------------------------
_token: str | None = None
_token_expires_at: float = 0.0
_token_lock = asyncio.Lock()

TOKEN_TTL = 55 * 60  # refresh 5 minutes before FedEx's 3600s expiry


async def _get_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expires_at

    async with _token_lock:
        if _token and time.monotonic() < _token_expires_at:
            return _token

        resp = await client.post(
            f"{settings.fedex_base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.fedex_client_id,
                "client_secret": settings.fedex_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data["access_token"]
        _token_expires_at = time.monotonic() + TOKEN_TTL
        logger.info("FedEx OAuth token refreshed.")
        return _token


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-locale": "en_US",
    }


# ---------------------------------------------------------------------------
# Public API methods
# ---------------------------------------------------------------------------

async def track_shipment(tracking_number: str) -> dict[str, Any]:
    """
    POST /track/v1/trackingnumbers
    Returns the raw FedEx tracking response for one tracking number.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _get_token(client)
        resp = await client.post(
            f"{settings.fedex_base_url}/track/v1/trackingnumbers",
            headers=_auth_headers(token),
            json={
                "includeDetailedScans": True,
                "trackingInfo": [
                    {
                        "trackingNumberInfo": {
                            "trackingNumber": tracking_number,
                        }
                    }
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()


async def subscribe_tracking_webhook(tracking_number: str, callback_url: str) -> dict[str, Any]:
    """
    POST /track/v1/notifications
    Ask FedEx to push updates to our webhook endpoint — real-time vs polling.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _get_token(client)
        resp = await client.post(
            f"{settings.fedex_base_url}/track/v1/notifications",
            headers=_auth_headers(token),
            json={
                "notificationEventTypes": [
                    "ON_ESTIMATED_DELIVERY",
                    "ON_EXCEPTION",
                    "ON_DELIVERY",
                    "ON_TENDER",
                    "ON_PICKUP",
                ],
                "trackingInfo": [{"trackingNumberInfo": {"trackingNumber": tracking_number}}],
                "notificationDetail": {
                    "notificationType": "REST",
                    "webhookDetail": {
                        "webhookURL": callback_url,
                        "secretKey": settings.fedex_webhook_secret,
                    },
                },
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_rate_quote(
    origin_zip: str,
    destination_zip: str,
    weight_lb: float,
    service_type: str = "FEDEX_GROUND",
) -> dict[str, Any]:
    """
    POST /rate/v1/rates/quotes
    Get a rate estimate — used to set expected_cost at ship time.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _get_token(client)
        resp = await client.post(
            f"{settings.fedex_base_url}/rate/v1/rates/quotes",
            headers=_auth_headers(token),
            json={
                "accountNumber": {"value": settings.fedex_account_number},
                "requestedShipment": {
                    "shipper": {"address": {"postalCode": origin_zip, "countryCode": "US"}},
                    "recipient": {"address": {"postalCode": destination_zip, "countryCode": "US"}},
                    "serviceType": service_type,
                    "requestedPackageLineItems": [
                        {
                            "weight": {"units": "LB", "value": weight_lb},
                        }
                    ],
                },
                "rateRequestType": ["LIST"],
            },
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Parsing helpers — normalize FedEx response into our internal format
# ---------------------------------------------------------------------------

def parse_tracking_events(fedex_response: dict) -> list[dict]:
    """Extract a clean list of events from a FedEx track response."""
    events = []
    try:
        results = fedex_response["output"]["completeTrackResults"][0]["trackResults"][0]
        scans = results.get("scanEvents", [])
        for scan in scans:
            loc_parts = [
                scan.get("scanLocation", {}).get("city", ""),
                scan.get("scanLocation", {}).get("stateOrProvinceCode", ""),
            ]
            events.append({
                "timestamp": scan.get("date"),
                "location": ", ".join(p for p in loc_parts if p) or None,
                "description": scan.get("eventDescription"),
                "event_code": scan.get("eventType"),
            })
    except (KeyError, IndexError):
        pass
    return events


def parse_status(fedex_response: dict) -> str | None:
    """Extract the top-level status code from a FedEx track response."""
    try:
        results = fedex_response["output"]["completeTrackResults"][0]["trackResults"][0]
        return results["latestStatusDetail"]["statusByLocale"]
    except (KeyError, IndexError):
        return None


def parse_estimated_delivery(fedex_response: dict) -> str | None:
    try:
        results = fedex_response["output"]["completeTrackResults"][0]["trackResults"][0]
        return results.get("estimatedDeliveryTimeWindow", {}).get("window", {}).get("ends")
    except (KeyError, IndexError):
        return None


def parse_rate(rate_response: dict) -> float | None:
    """Pull the total net charge from a rate quote response."""
    try:
        detail = rate_response["output"]["rateReplyDetails"][0]["ratedShipmentDetails"][0]
        return float(detail["totalNetCharge"])
    except (KeyError, IndexError, ValueError):
        return None
