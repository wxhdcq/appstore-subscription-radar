from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ApiModel(BaseModel):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_utc_datetimes(self, value):
        if not isinstance(value, datetime):
            return value
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")


class AppCreate(ApiModel):
    apple_id: str = Field(pattern=r"^\d{6,20}$")
    name: str = "待刷新应用"
    developer: str = ""
    icon_url: str = ""


class AppOut(ApiModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    apple_id: str
    name: str
    developer: str
    icon_url: str
    enabled: bool
    last_refresh_at: datetime | None
    last_refresh_status: str


class SearchResult(ApiModel):
    apple_id: str
    name: str
    developer: str
    icon_url: str
    app_store_url: str


class PriceOut(ApiModel):
    storefront: str
    storefront_name: str
    amount: Decimal
    currency: str
    amount_cny: Decimal | None
    amount_usd: Decimal | None
    price_formatted: str
    localized_name: str
    fetched_at: datetime
    is_lowest: bool = False
    versus_lowest_percent: Decimal | None = None


class ProductOut(ApiModel):
    id: int
    apple_iap_id: str
    canonical_name: str
    period: str
    is_subscription: bool
    group_name: str
    prices: list[PriceOut]


class AppDetail(AppOut):
    products: list[ProductOut]


class RefreshResult(ApiModel):
    app_id: int
    storefront_total: int
    storefront_success: int
    products_seen: int
    errors: list[str]
