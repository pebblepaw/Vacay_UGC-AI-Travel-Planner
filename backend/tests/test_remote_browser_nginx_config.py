from pathlib import Path


def test_nginx_proxies_root_websockify_to_browser_worker() -> None:
    config = Path("deploy/nginx/default.conf").read_text()

    assert "location /websockify" in config
    assert "proxy_pass http://browser-worker:7900" in config
    assert "proxy_set_header Upgrade $http_upgrade;" in config
    assert 'proxy_set_header Connection "upgrade";' in config
