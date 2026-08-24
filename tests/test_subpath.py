from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_frontend_uses_subpath_safe_relative_urls() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'href="./static/styles.css' in html
    assert 'src="./static/app.js' in html
    assert 'href="./docs"' in html
    assert "path.replace(/^\\/+/, \"\")" in javascript

