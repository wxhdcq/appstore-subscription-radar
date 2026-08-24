from contextlib import asynccontextmanager
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import DEFAULT_STOREFRONTS, STOREFRONT_NAMES, get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import App, CurrentPrice, PriceSnapshot, Product
from .scheduler import build_scheduler
from .schemas import AppCreate, AppDetail, AppOut, RefreshResult, SearchResult
from .services.apple import AppleCatalogClient
from .services.refresh import refresh_app

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEMO_APPS = (
    ("6448311069", "ChatGPT"),
    ("324684580", "Spotify"),
    ("1232780281", "Notion"),
    ("544007664", "YouTube"),
    ("930441707", "Bumble"),
    ("547702041", "Tinder"),
)


def as_utc(value):
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def seed_demo_apps() -> None:
    settings = get_settings()
    if not settings.seed_demo_apps:
        return
    with SessionLocal() as db:
        existing_ids = set(db.scalars(select(App.apple_id)))
        for apple_id, name in DEMO_APPS:
            if apple_id not in existing_ids:
                db.add(App(apple_id=apple_id, name=name))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_demo_apps()
    scheduler = build_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(
    title="App Store 全球订阅雷达 API",
    version="0.1.1",
    root_path=settings.root_path,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
DbSession = Annotated[Session, Depends(get_db)]


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_token
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理令牌无效")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health(db: DbSession) -> dict:
    db.scalar(select(func.count()).select_from(App))
    return {"ok": True, "version": app.version}


@app.get("/api/storefronts")
def storefronts() -> list[dict[str, str]]:
    return [{"code": code, "name": STOREFRONT_NAMES.get(code, code)} for code in DEFAULT_STOREFRONTS]


@app.get("/api/search", response_model=list[SearchResult])
async def search_apps(q: str = Query(min_length=1, max_length=200), country: str = "US") -> list[dict[str, str]]:
    client = AppleCatalogClient()
    try:
        return await client.search(q, country)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Apple 搜索暂时不可用：{exc}") from exc
    finally:
        await client.aclose()


@app.get("/api/apps", response_model=list[AppOut])
def list_apps(db: DbSession) -> list[App]:
    return list(db.scalars(select(App).order_by(App.name)))


@app.post("/api/apps", response_model=AppOut, status_code=201, dependencies=[Depends(require_admin)])
def create_app(payload: AppCreate, db: DbSession) -> App:
    existing = db.scalar(select(App).where(App.apple_id == payload.apple_id))
    if existing:
        return existing
    record = App(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _serialize_detail(record: App, db: Session) -> dict:
    products = list(db.scalars(select(Product).where(Product.app_id == record.id).order_by(Product.canonical_name)))
    product_payloads = []
    for product in products:
        prices = list(
            db.scalars(
                select(CurrentPrice)
                .where(CurrentPrice.product_id == product.id)
                .order_by(CurrentPrice.amount_cny.asc().nulls_last())
            )
        )
        comparable = [price.amount_cny for price in prices if price.amount_cny is not None and price.amount_cny > 0]
        lowest = min(comparable) if comparable else None
        price_payloads = []
        for price in prices:
            difference = None
            if lowest and price.amount_cny is not None:
                difference = ((price.amount_cny / lowest) - Decimal("1")) * Decimal("100")
                difference = difference.quantize(Decimal("0.1"))
            price_payloads.append(
                {
                    "storefront": price.storefront,
                    "storefront_name": STOREFRONT_NAMES.get(price.storefront, price.storefront),
                    "amount": price.amount,
                    "currency": price.currency,
                    "amount_cny": price.amount_cny,
                    "amount_usd": price.amount_usd,
                    "price_formatted": price.price_formatted,
                    "localized_name": price.localized_name,
                    "fetched_at": price.fetched_at,
                    "is_lowest": lowest is not None and price.amount_cny == lowest,
                    "versus_lowest_percent": difference,
                }
            )
        product_payloads.append(
            {
                "id": product.id,
                "apple_iap_id": product.apple_iap_id,
                "canonical_name": product.canonical_name,
                "period": product.period,
                "is_subscription": product.is_subscription,
                "group_name": product.group_name,
                "prices": price_payloads,
            }
        )
    return {
        "id": record.id,
        "apple_id": record.apple_id,
        "name": record.name,
        "developer": record.developer,
        "icon_url": record.icon_url,
        "enabled": record.enabled,
        "last_refresh_at": record.last_refresh_at,
        "last_refresh_status": record.last_refresh_status,
        "products": product_payloads,
    }


@app.get("/api/apps/{app_id}", response_model=AppDetail)
def app_detail(app_id: int, db: DbSession) -> dict:
    record = db.get(App, app_id)
    if not record:
        raise HTTPException(status_code=404, detail="应用不存在")
    return _serialize_detail(record, db)


@app.post("/api/apps/{app_id}/refresh", response_model=RefreshResult, dependencies=[Depends(require_admin)])
async def refresh_app_endpoint(
    app_id: int,
    regions: str | None = Query(default=None, description="逗号分隔的二位地区码"),
) -> dict:
    requested = tuple(dict.fromkeys(code.strip().upper() for code in (regions or "").split(",") if code.strip()))
    selected = requested or DEFAULT_STOREFRONTS
    invalid = [code for code in selected if code not in STOREFRONT_NAMES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"暂不支持地区：{', '.join(invalid)}")
    try:
        return await refresh_app(app_id, selected)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"刷新失败：{exc}") from exc


@app.get("/api/products/{product_id}/history")
def product_history(product_id: int, db: DbSession, storefront: str | None = None) -> list[dict]:
    query = select(PriceSnapshot).where(PriceSnapshot.product_id == product_id)
    if storefront:
        query = query.where(PriceSnapshot.storefront == storefront.upper())
    rows = list(db.scalars(query.order_by(PriceSnapshot.fetched_at.desc()).limit(500)))
    return [
        {
            "storefront": row.storefront,
            "amount": row.amount,
            "currency": row.currency,
            "amount_cny": row.amount_cny,
            "amount_usd": row.amount_usd,
            "change_kind": row.change_kind,
            "fetched_at": as_utc(row.fetched_at),
        }
        for row in rows
    ]


@app.get("/api/stats")
def stats(db: DbSession) -> dict:
    return {
        "apps": db.scalar(select(func.count()).select_from(App)) or 0,
        "products": db.scalar(select(func.count()).select_from(Product)) or 0,
        "current_prices": db.scalar(select(func.count()).select_from(CurrentPrice)) or 0,
        "snapshots": db.scalar(select(func.count()).select_from(PriceSnapshot)) or 0,
        "storefronts": len(DEFAULT_STOREFRONTS),
    }
