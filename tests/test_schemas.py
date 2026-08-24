from datetime import datetime

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
