from pathlib import Path


def test_browser_worker_waits_for_x_server_and_chrome_process():
    script = Path("deploy/browser-worker/start.sh").read_text()

    assert "xdpyinfo -display" in script
    assert 'wait "$chrome_pid"' in script
    assert "wait -n" not in script


def test_browser_worker_proxies_cdp_port_for_other_containers():
    script = Path("deploy/browser-worker/start.sh").read_text()
    dockerfile = Path("deploy/browser-worker/Dockerfile").read_text()

    assert "--remote-debugging-port=9223" in script
    assert "socat TCP-LISTEN:9222" in script
    assert "TCP:127.0.0.1:9223" in script
    assert "socat" in dockerfile


def test_browser_worker_clears_stale_chromium_profile_locks():
    script = Path("deploy/browser-worker/start.sh").read_text()

    assert "SingletonLock" in script
    assert "SingletonSocket" in script
    assert "SingletonCookie" in script
    assert "rm -f" in script
