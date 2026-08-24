from pathlib import Path


def test_nginx_proxy_preserves_subpath_prefix() -> None:
    config = Path("deploy/nginx-appstore-radar.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://127.0.0.1:8766;" in config
    assert "proxy_pass http://127.0.0.1:8766/;" not in config
