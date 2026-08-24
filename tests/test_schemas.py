from datetime import datetime

from app.config import Settings
from app.schemas import AppOut


def test_api_datetime_is_serialized_as_utc() -> None:
    app = AppOut(
        id=1,
        apple_id="6448311069",
        name="ChatGPT",
        developer="OpenAI",
        icon_url="",
        enabled=True,
        last_refresh_at=datetime(2026, 8, 24, 16, 30),
        last_refresh_status="ok",
    )

    assert '"last_refresh_at":"2026-08-24T16:30:00Z"' in app.model_dump_json()


def test_root_path_is_normalized() -> None:
    assert Settings(root_path="appstore-radar/").root_path == "/appstore-radar"
    assert Settings(root_path="/").root_path == ""
