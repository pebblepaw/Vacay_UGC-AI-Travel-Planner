"""Remote browser takeover endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.services.browser_takeover import browser_takeover_service


router = APIRouter(prefix="/api/browser", tags=["browser"])


@router.get("/takeover")
async def get_browser_takeover(token: str = Query(...)):
    payload = await browser_takeover_service.get_takeover_payload(token)
    if payload is None:
        raise HTTPException(status_code=403, detail="Invalid browser takeover token")
    return payload
