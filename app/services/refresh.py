import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from ..config import DEFAULT_STOREFRONTS
from ..database import SessionLocal
from ..models import App, CurrentPrice, FetchRun, PriceSnapshot, Product
from .apple import AppleCatalogClient
from .fx import FxService


def _same_price(current: CurrentPrice, amount: Decimal, currency: str) -> bool:
    return current.currency == currency and current.amount == amount


async def refresh_app(app_id: int, storefronts: tuple[str, ...] = DEFAULT_STOREFRONTS) -> dict:
    db = SessionLocal()
    run: FetchRun | None = None
    try:
        app = db.get(App, app_id)
        if not app:
            raise ValueError(f"App {app_id} 不存在")
        run = FetchRun(app_id=app.id, storefront_total=len(storefronts))
        db.add(run)
        db.commit()
        db.refresh(run)

        client = AppleCatalogClient()
        fx = FxService()
        metadata_task = client.fetch_metadata(app.apple_id)
        rates_task = fx.get_rates()
        results_task = asyncio.gather(*(client.fetch_iaps(app.apple_id, code) for code in storefronts))
        try:
            metadata, rates, results = await asyncio.gather(metadata_task, rates_task, results_task)
        finally:
            await client.aclose()

        if metadata:
            app.name = metadata.get("name") or app.name
            app.developer = metadata.get("developer") or app.developer
            app.icon_url = metadata.get("icon_url") or app.icon_url

        product_cache: dict[tuple[str, str], Product] = {}
        success_count = 0
        products_seen = 0
        errors: list[str] = []
        now = datetime.now(UTC)

        for result in results:
            if not result.ok:
                errors.append(f"{result.storefront}: {result.error}")
                continue
            success_count += 1
            for item in result.iaps or []:
                if not item.iap_id:
                    continue
                key = (item.iap_id, item.period)
                product = product_cache.get(key)
                if product is None:
                    product = db.scalar(
                        select(Product).where(
                            Product.app_id == app.id,
                            Product.apple_iap_id == item.iap_id,
                            Product.period == item.period,
                        )
                    )
                    if product is None:
                        product = Product(
                            app_id=app.id,
                            apple_iap_id=item.iap_id,
                            canonical_name=item.name,
                            period=item.period,
                            is_subscription=item.is_subscription,
                            group_name=item.group_name,
                        )
                        db.add(product)
                        db.flush()
                    elif result.storefront in {"US", "GB", "CA", "AU"}:
                        product.canonical_name = item.name
                    product_cache[key] = product
                    products_seen += 1

                amount_cny = fx.convert(item.amount, item.currency, "CNY", rates)
                amount_usd = fx.convert(item.amount, item.currency, "USD", rates)
                current = db.scalar(
                    select(CurrentPrice).where(
                        CurrentPrice.product_id == product.id,
                        CurrentPrice.storefront == result.storefront,
                    )
                )
                change_kind = "initial"
                changed = current is None
                if current is None:
                    current = CurrentPrice(
                        product_id=product.id,
                        storefront=result.storefront,
                        amount=item.amount,
                        currency=item.currency,
                    )
                    db.add(current)
                elif not _same_price(current, item.amount, item.currency):
                    change_kind = "price_change"
                    changed = True

                current.localized_name = item.name
                current.amount = item.amount
                current.currency = item.currency
                current.amount_cny = amount_cny
                current.amount_usd = amount_usd
                current.price_formatted = item.formatted
                current.fetched_at = now

                if changed:
                    db.add(
                        PriceSnapshot(
                            product_id=product.id,
                            storefront=result.storefront,
                            amount=item.amount,
                            currency=item.currency,
                            amount_cny=amount_cny,
                            amount_usd=amount_usd,
                            change_kind=change_kind,
                            fetched_at=now,
                        )
                    )

        app.last_refresh_at = now
        app.last_refresh_status = "ok" if success_count else "failed"
        run.finished_at = now
        run.status = "ok" if success_count else "failed"
        run.storefront_success = success_count
        run.products_seen = products_seen
        run.error_summary = "\n".join(errors[:20])
        db.commit()
        return {
            "app_id": app.id,
            "storefront_total": len(storefronts),
            "storefront_success": success_count,
            "products_seen": products_seen,
            "errors": errors,
        }
    except Exception as exc:
        db.rollback()
        if run is not None:
            failed_run = db.get(FetchRun, run.id)
            if failed_run:
                failed_run.status = "failed"
                failed_run.finished_at = datetime.now(UTC)
                failed_run.error_summary = str(exc)
                db.commit()
        raise
    finally:
        db.close()


async def refresh_all_apps() -> None:
    with SessionLocal() as db:
        app_ids = list(db.scalars(select(App.id).where(App.enabled.is_(True))))
    for app_id in app_ids:
        try:
            await refresh_app(app_id)
        except Exception:
            continue
