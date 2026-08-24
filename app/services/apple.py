import asyncio
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ..config import get_settings

APPLE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


@dataclass(slots=True)
class AppleIAP:
    iap_id: str
    name: str
    period: str
    is_subscription: bool
    group_name: str
    amount: Decimal
    currency: str
    formatted: str


@dataclass(slots=True)
class StorefrontResult:
    storefront: str
    app_name: str = ""
    iaps: list[AppleIAP] | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


class AppleCatalogClient:
    """访问 Apple 公开搜索接口和 App Store 网页 Catalog 接口。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.request_timeout_seconds
        self.semaphore = asyncio.Semaphore(settings.request_concurrency)
        self.headers = {
            "User-Agent": APPLE_USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(self, term: str, country: str = "US") -> list[dict[str, str]]:
        term = term.strip()
        if not term:
            return []
        app_id_match = re.search(r"id(\d{6,20})|^(\d{6,20})$", term)
        if app_id_match:
            app_id = app_id_match.group(1) or app_id_match.group(2)
            url = "https://itunes.apple.com/lookup"
            params = {"id": app_id, "country": country.lower(), "entity": "software"}
        else:
            url = "https://itunes.apple.com/search"
            params = {
                "term": term,
                "country": country.lower(),
                "entity": "software",
                "limit": 12,
            }
        response = await self._http().get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        return [
            {
                "apple_id": str(item.get("trackId", "")),
                "name": item.get("trackName", ""),
                "developer": item.get("artistName", ""),
                "icon_url": item.get("artworkUrl100", ""),
                "app_store_url": item.get("trackViewUrl", ""),
            }
            for item in payload.get("results", [])
            if item.get("trackId")
        ]

    async def fetch_metadata(self, apple_id: str, country: str = "US") -> dict[str, str]:
        results = await self.search(apple_id, country)
        return results[0] if results else {}

    async def fetch_iaps(self, apple_id: str, storefront: str) -> StorefrontResult:
        storefront = storefront.upper()
        url = f"https://apps.apple.com/api/apps/v1/catalog/{storefront.lower()}/apps/{apple_id}"
        params = {"platform": "web", "views": "top-in-app-purchasables", "l": "en-us"}
        headers = {
            **self.headers,
            "Authorization": "Bearer",
            "Referer": f"https://apps.apple.com/{storefront.lower()}/app/id{apple_id}",
        }
        try:
            async with self.semaphore:
                response = await self._http().get(url, params=params, headers=headers)
            if response.status_code == 404:
                return StorefrontResult(storefront=storefront, error="未上架或无公开数据")
            response.raise_for_status()
            return self._parse_iaps(storefront, response.json())
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return StorefrontResult(storefront=storefront, error=f"{type(exc).__name__}: {exc}")

    def _parse_iaps(self, storefront: str, payload: dict[str, Any]) -> StorefrontResult:
        data = payload.get("data") or []
        if not data:
            return StorefrontResult(storefront=storefront, error="Apple 返回空数据")
        app = data[0]
        app_name = app.get("attributes", {}).get("name", "")
        view = app.get("views", {}).get("top-in-app-purchasables", {})
        raw_iaps = view.get("data") or []
        parsed: list[AppleIAP] = []
        for item in raw_iaps:
            attributes = item.get("attributes", {})
            for offer in attributes.get("offers") or []:
                try:
                    amount = Decimal(str(offer.get("price")))
                except (InvalidOperation, TypeError):
                    continue
                currency = str(offer.get("currencyCode") or "").upper()
                if not currency:
                    continue
                parsed.append(
                    AppleIAP(
                        iap_id=str(item.get("id") or ""),
                        name=str(attributes.get("name") or attributes.get("offerName") or "未命名订阅"),
                        period=str(offer.get("recurringSubscriptionPeriod") or "ONCE"),
                        is_subscription=bool(attributes.get("isSubscription", False)),
                        group_name=str(attributes.get("subscriptionFamilyName") or ""),
                        amount=amount,
                        currency=currency,
                        formatted=str(offer.get("priceFormatted") or ""),
                    )
                )
        return StorefrontResult(storefront=storefront, app_name=app_name, iaps=parsed)
