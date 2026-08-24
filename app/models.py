from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class App(Base):
    __tablename__ = "apps"

    id: Mapped[int] = mapped_column(primary_key=True)
    apple_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    developer: Mapped[str] = mapped_column(String(240), default="")
    icon_url: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_status: Mapped[str] = mapped_column(String(32), default="pending")

    products: Mapped[list["Product"]] = relationship(back_populates="app", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("app_id", "apple_iap_id", "period", name="uq_product_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    apple_iap_id: Mapped[str] = mapped_column(String(64))
    canonical_name: Mapped[str] = mapped_column(String(300))
    period: Mapped[str] = mapped_column(String(24), default="ONCE")
    is_subscription: Mapped[bool] = mapped_column(Boolean, default=False)
    group_name: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    app: Mapped[App] = relationship(back_populates="products")
    current_prices: Mapped[list["CurrentPrice"]] = relationship(cascade="all, delete-orphan")
    snapshots: Mapped[list["PriceSnapshot"]] = relationship(cascade="all, delete-orphan")


class CurrentPrice(Base):
    __tablename__ = "current_prices"
    __table_args__ = (
        UniqueConstraint("product_id", "storefront", name="uq_current_product_storefront"),
        Index("ix_current_storefront_amount", "storefront", "amount_cny"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    storefront: Mapped[str] = mapped_column(String(2), index=True)
    localized_name: Mapped[str] = mapped_column(String(300), default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    amount_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_formatted: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[str] = mapped_column(String(40), default="apple_web_catalog")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_snapshot_product_storefront_time", "product_id", "storefront", "fetched_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    storefront: Mapped[str] = mapped_column(String(2), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    amount_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    change_kind: Mapped[str] = mapped_column(String(32), default="initial")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FetchRun(Base):
    __tablename__ = "fetch_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int | None] = mapped_column(ForeignKey("apps.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    storefront_total: Mapped[int] = mapped_column(default=0)
    storefront_success: Mapped[int] = mapped_column(default=0)
    products_seen: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str] = mapped_column(Text, default="")

