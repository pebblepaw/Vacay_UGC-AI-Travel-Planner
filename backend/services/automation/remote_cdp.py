from __future__ import annotations

import ipaddress
import socket
from urllib.parse import SplitResult, urlsplit, urlunsplit


def resolve_remote_cdp_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw

    parts = urlsplit(raw)
    host = parts.hostname or ""
    if not host:
        return raw

    try:
        ipaddress.ip_address(host)
        return raw
    except ValueError:
        pass

    if host.lower() == "localhost":
        return raw

    try:
        resolved_host = socket.gethostbyname(host)
    except OSError:
        return raw

    netloc = resolved_host
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials = f"{credentials}:{parts.password}"
        netloc = f"{credentials}@{netloc}"

    return urlunsplit(
        SplitResult(
            scheme=parts.scheme,
            netloc=netloc,
            path=parts.path,
            query=parts.query,
            fragment=parts.fragment,
        )
    )
