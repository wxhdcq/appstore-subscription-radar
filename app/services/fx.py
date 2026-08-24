from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from ..config import get_settings


class FxService:
    """获取 USD 基准汇率；短时缓存避免每个 App 重复请求。"""

    _rates: dict[str, Decimal] = {"USD": Decimal("1")}
    _updated_at: datetime | None = None

    async def get_rates(self) -> dict[str, Decimal]:
        cache = type(self)
        now = datetime.now(UTC)
        if cache._updated_at and now - cache._updated_at < timedelta(hours=6):
            return cache._rates

        settings = get_settings()
        urls = (
            "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json",
            "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
        )
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    values = response.json().get("usd") or {}
                    rates = {"USD": Decimal("1")}
                    for code, value in values.items():
                        try:
                            rates[code.upper()] = Decimal(str(value))
                        except (InvalidOperation, TypeError):
                            continue
                    if "CNY" in rates:
                        cache._rates = rates
                        cache._updated_at = now
                        return rates
                except (httpx.HTTPError, ValueError):
                    continue
        return cache._rates

    @staticmethod
    def convert(amount: Decimal, currency: str, target: str, rates: dict[str, Decimal]) -> Decimal | None:
        source_rate = rates.get(currency.upper())
        target_rate = rates.get(target.upper())
        if not source_rate or not target_rate:
            return None
        return (amount / source_rate * target_rate).quantize(Decimal("0.000001"))
