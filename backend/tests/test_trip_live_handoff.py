import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import backend.services.automation.browser_use_worker as browser_use_worker_module
import backend.services.automation.playwright_checkout as playwright_checkout_module
from backend.services.automation.browser_use_worker import BookingQuery, BrowserUseWorker
from backend.services.automation.live_booking_sessions import live_booking_sessions
from backend.services.automation.playwright_checkout import PlaywrightCheckoutRunner


class FakeTextNode:
    def __init__(self, text: str = "", href: str = "") -> None:
        self._text = text
        self._href = href

    async def inner_text(self) -> str:
        return self._text

    async def get_attribute(self, name: str) -> str | None:
        if name == "href":
            return self._href
        return None


class FakeCard:
    def __init__(self, *, card_id: str, text: str, href: str = "") -> None:
        self._card_id = card_id
        self._text = text
        self._href = href

    async def get_attribute(self, name: str) -> str | None:
        if name == "id":
            return self._card_id
        return None

    async def inner_text(self) -> str:
        return self._text

    async def query_selector(self, selector: str):
        if selector == "a" and self._href:
            return FakeTextNode(href=self._href)
        return None

    async def query_selector_all(self, selector: str):
        return []


class FakeResultsPage:
    def __init__(self, url: str, cards: list[FakeCard]) -> None:
        self.url = url
        self._cards = cards

    async def query_selector_all(self, selector: str):
        if selector == "[data-testid^='u-flight-card-']":
            return self._cards
        return []


class FakeSearchPage:
    def __init__(self) -> None:
        self.url = "https://www.trip.com/flights/showfarefirst/?dcity=SIN&acity=NRT"
        self.screenshots: list[str] = []

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.url = url

    async def title(self) -> str:
        return "Flights from Singapore to Tokyo"

    async def screenshot(self, path: str, full_page: bool) -> None:
        self.screenshots.append(path)

    async def bring_to_front(self) -> None:
        return None


class FakeBrowser:
    def __init__(self, page: FakeSearchPage) -> None:
        self.page = page
        self.closed = False

    async def new_page(self) -> FakeSearchPage:
        return self.page

    async def close(self) -> None:
        self.closed = True
        return None


class FakeModalButton:
    def __init__(
        self,
        *,
        text: str,
        aria_label: str = "",
        visible: bool = True,
        on_click=None,
    ) -> None:
        self._text = text
        self._aria_label = aria_label
        self._visible = visible
        self._on_click = on_click

    async def is_visible(self) -> bool:
        return self._visible

    async def inner_text(self) -> str:
        return self._text

    async def get_attribute(self, name: str) -> str | None:
        if name == "aria-label":
            return self._aria_label
        return None

    async def click(self, timeout: int = 0) -> None:
        if self._on_click is not None:
            self._on_click()


class FakeModalButtons:
    def __init__(self, buttons: list[FakeModalButton]) -> None:
        self._buttons = buttons

    async def count(self) -> int:
        return len(self._buttons)

    def nth(self, index: int) -> FakeModalButton:
        return self._buttons[index]


class FakeModalContainer:
    def __init__(self, buttons: list[FakeModalButton]) -> None:
        self._buttons = buttons

    async def count(self) -> int:
        return 1 if self._buttons else 0

    @property
    def last(self) -> "FakeModalContainer":
        return self

    def locator(self, selector: str):
        if selector == "button":
            return FakeModalButtons(self._buttons)
        raise AssertionError(f"Unexpected nested selector: {selector}")


class FakeResultsModalPage:
    def __init__(self) -> None:
        self.url = "https://www.trip.com/flights/showfarefirst/?dcity=SIN&acity=SYD"
        self._buttons = [
            FakeModalButton(text="", aria_label="close"),
            FakeModalButton(
                text="",
                aria_label="continue",
                on_click=lambda: setattr(
                    self,
                    "url",
                    "https://www.trip.com/flights/passenger?booking=123",
                ),
            ),
        ]

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        return None

    def locator(self, selector: str):
        if selector in {
            "[role='dialog']",
            "[aria-modal='true']",
            "div[class*='modal']",
            "div[class*='dialog']",
            "div[class*='drawer']",
        }:
            return FakeModalContainer(self._buttons)
        raise AssertionError(f"Unexpected selector: {selector}")


class FakeChromium:
    def __init__(self, page: FakeSearchPage) -> None:
        self.page = page
        self.launch_kwargs = None
        self.cdp_endpoint = None

    async def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return FakeBrowser(self.page)

    async def connect_over_cdp(self, endpoint: str):
        self.cdp_endpoint = endpoint
        browser = FakeBrowser(self.page)
        browser.contexts = [SimpleNamespace(pages=[self.page])]
        return browser


class FakeAsyncPlaywright:
    def __init__(self, page: FakeSearchPage) -> None:
        self.chromium = FakeChromium(page)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


def test_trip_search_launches_visible_browser(monkeypatch) -> None:
    worker = BrowserUseWorker()
    fake_page = FakeSearchPage()
    fake_async_playwright = FakeAsyncPlaywright(fake_page)
    fake_module = types.ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: fake_async_playwright
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    monkeypatch.setattr(worker, "_save_trip_debug", AsyncMock())
    monkeypatch.setattr(worker, "_wait_for_trip_results", AsyncMock())
    monkeypatch.setattr(worker, "_is_trip_homepage", AsyncMock(return_value=False))
    monkeypatch.setattr(
        worker,
        "_scrape_trip_cards",
        AsyncMock(
            return_value=[
                {
                    "id": "offer_1",
                    "title": "Demo Flight",
                    "price": 321.0,
                    "currency": "USD",
                    "provider": "trip.com",
                    "deeplink": "https://www.trip.com/flights/passenger?booking=123",
                }
            ]
        ),
    )

    query = BookingQuery(
        booking_type="flight",
        origin="Singapore",
        destination="Tokyo",
        departure_date="2026-05-01",
        return_date="",
        adults=1,
        budget_limit=0.0,
        provider_hint="trip.com",
        max_results=3,
    )

    offers = asyncio.run(worker._search_with_playwright(query))

    assert offers
    assert fake_async_playwright.chromium.launch_kwargs["headless"] is False


def test_trip_search_uses_remote_browser_worker_when_cdp_url_is_configured(monkeypatch) -> None:
    worker = BrowserUseWorker()
    fake_page = FakeSearchPage()
    fake_async_playwright = FakeAsyncPlaywright(fake_page)
    fake_module = types.ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: fake_async_playwright
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)
    monkeypatch.setattr(
        browser_use_worker_module,
        "settings",
        SimpleNamespace(REMOTE_BROWSER_CDP_URL="http://browser-worker:9222"),
        raising=False,
    )

    monkeypatch.setattr(worker, "_save_trip_debug", AsyncMock())
    monkeypatch.setattr(worker, "_wait_for_trip_results", AsyncMock())
    monkeypatch.setattr(worker, "_is_trip_homepage", AsyncMock(return_value=False))
    monkeypatch.setattr(
        worker,
        "_scrape_trip_cards",
        AsyncMock(
            return_value=[
                {
                    "id": "offer_1",
                    "title": "Demo Flight",
                    "price": 321.0,
                    "currency": "USD",
                    "provider": "trip.com",
                    "deeplink": "https://www.trip.com/flights/passenger?booking=123",
                }
            ]
        ),
    )

    query = BookingQuery(
        booking_type="flight",
        origin="Singapore",
        destination="Tokyo",
        departure_date="2026-05-01",
        return_date="",
        adults=1,
        budget_limit=0.0,
        provider_hint="trip.com",
        max_results=3,
    )

    offers = asyncio.run(worker._search_with_playwright(query))

    assert offers
    assert fake_async_playwright.chromium.cdp_endpoint == "http://browser-worker:9222"


def test_trip_search_marks_results_page_reference_as_live_session_only() -> None:
    worker = BrowserUseWorker()
    query = BookingQuery(
        booking_type="flight",
        origin="Singapore",
        destination="Tokyo",
        departure_date="2026-05-01",
        return_date="",
        adults=1,
        budget_limit=0.0,
        provider_hint="trip.com",
        max_results=3,
    )
    page = FakeResultsPage(
        "https://www.trip.com/flights/showfarefirst/?dcity=SIN&acity=NRT",
        [FakeCard(card_id="card-1", text="Scoot SIN NRT USD 199")],
    )

    offers = asyncio.run(worker._scrape_trip_cards(page, query))

    assert offers[0]["deeplink"] == ""
    assert offers[0]["handoff_mode"] == "live_session_only"
    assert offers[0]["results_page_url"] == page.url
    assert offers[0]["requires_live_session"] is True


def test_checkout_fails_honestly_when_live_session_only_offer_loses_session() -> None:
    runner = PlaywrightCheckoutRunner()
    offer = {
        "id": "offer_1",
        "title": "Demo Flight",
        "provider": "trip.com",
        "deeplink": "",
        "handoff_mode": "live_session_only",
        "results_page_url": "https://www.trip.com/flights/showfarefirst/?dcity=SIN&acity=NRT",
        "live_session_id": "trip-session-1",
        "requires_live_session": True,
    }

    result = asyncio.run(
        runner.checkout_to_confirmation(
            offer,
            traveler={},
            headless=False,
            skip_fill=True,
        )
    )

    assert result["status"] == "failed"
    assert "live session" in result["reason"].lower()
    assert "results page" in result["reason"].lower()


def test_checkout_reuses_live_session_page_when_available(monkeypatch) -> None:
    runner = PlaywrightCheckoutRunner()
    fake_page = FakeSearchPage()
    fake_browser = FakeBrowser(fake_page)

    async def register_session():
        return await live_booking_sessions.register(
            provider="trip.com",
            playwright=types.SimpleNamespace(),
            browser=fake_browser,
            page=fake_page,
            query_summary="Singapore->Tokyo",
        )

    session = asyncio.run(register_session())
    selected = AsyncMock()

    async def fake_checkout_flow(page, traveler, skip_fill=False):
        page.url = "https://www.trip.com/flights/passenger?booking=123"

    monkeypatch.setattr(runner, "_trip_select_offer_on_results", selected)
    monkeypatch.setattr(runner, "_trip_checkout_flow", fake_checkout_flow)

    offer = {
        "id": "offer_1",
        "title": "Demo Flight",
        "provider": "trip.com",
        "deeplink": "",
        "handoff_mode": "live_session_only",
        "results_page_url": fake_page.url,
        "live_session_id": session.session_id,
        "requires_live_session": True,
        "card_selector": "[data-testid='u-flight-card-1']",
    }

    result = asyncio.run(
        runner.checkout_to_confirmation(
            offer,
            traveler={},
            headless=False,
            skip_fill=True,
        )
    )

    assert result["status"] == "needs_user_input"
    assert result["handoff_channel"] == "live_browser"
    selected.assert_awaited_once()
    assert fake_browser.closed is False

    asyncio.run(live_booking_sessions.close(session.session_id))


def test_trip_checkout_advances_results_fare_modal_when_primary_button_has_no_text(monkeypatch) -> None:
    runner = PlaywrightCheckoutRunner()
    page = FakeResultsModalPage()

    monkeypatch.setattr(runner, "_handle_cookie_banner", AsyncMock())
    monkeypatch.setattr(runner, "_wait_for_checkout_start", AsyncMock())
    monkeypatch.setattr(runner, "_click_first_available", AsyncMock(return_value=False))
    monkeypatch.setattr(runner, "_trip_handle_baggage", AsyncMock())
    fill_mock = AsyncMock()
    monkeypatch.setattr(runner, "_fill_traveler_form", fill_mock)

    asyncio.run(runner._trip_checkout_flow(page, traveler={}, skip_fill=True))

    assert "/flights/passenger" in page.url
    fill_mock.assert_not_awaited()


def test_checkout_returns_signed_takeover_page_for_remote_browser_handoff(monkeypatch) -> None:
    runner = PlaywrightCheckoutRunner()
    fake_page = FakeSearchPage()
    fake_browser = FakeBrowser(fake_page)

    async def register_session():
        return await live_booking_sessions.register(
            provider="trip.com",
            playwright=types.SimpleNamespace(),
            browser=fake_browser,
            page=fake_page,
            query_summary="Singapore->Sydney",
        )

    session = asyncio.run(register_session())

    async def fake_checkout_flow(page, traveler, skip_fill=False):
        page.url = "https://www.trip.com/flights/passenger?booking=remote-123"

    monkeypatch.setattr(runner, "_trip_select_offer_on_results", AsyncMock())
    monkeypatch.setattr(runner, "_trip_checkout_flow", fake_checkout_flow)
    monkeypatch.setattr(
        playwright_checkout_module,
        "settings",
        SimpleNamespace(
            PUBLIC_WEB_BASE_URL="https://demo.vacay.ai",
            PUBLIC_REMOTE_BROWSER_URL="https://demo.vacay.ai/remote-browser/vnc.html",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "backend.services.automation.playwright_checkout.browser_takeover_service",
        SimpleNamespace(
            enabled=True,
            create_takeover_url=AsyncMock(
                return_value="https://demo.vacay.ai/browser?token=signed-browser-token"
            ),
        ),
        raising=False,
    )

    offer = {
        "id": "offer_remote_1",
        "title": "Remote Demo Flight",
        "provider": "trip.com",
        "deeplink": "",
        "handoff_mode": "live_session_only",
        "results_page_url": fake_page.url,
        "live_session_id": session.session_id,
        "requires_live_session": True,
        "card_selector": "[data-testid='u-flight-card-1']",
    }

    result = asyncio.run(
        runner.checkout_to_confirmation(
            offer,
            traveler={},
            headless=False,
            skip_fill=True,
        )
    )

    assert result["status"] == "needs_user_input"
    assert result["handoff_channel"] == "remote_browser"
    assert result["confirmation_url"] == "https://demo.vacay.ai/browser?token=signed-browser-token"

    asyncio.run(live_booking_sessions.close(session.session_id))


def test_checkout_reconnects_remote_browser_when_live_session_registry_is_empty(monkeypatch) -> None:
    runner = PlaywrightCheckoutRunner()
    fake_page = FakeSearchPage()
    fake_async_playwright = FakeAsyncPlaywright(fake_page)
    fake_module = types.ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: fake_async_playwright
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)
    monkeypatch.setattr(
        playwright_checkout_module,
        "settings",
        SimpleNamespace(
            REMOTE_BROWSER_CDP_URL="http://browser-worker:9222",
            PUBLIC_WEB_BASE_URL="https://demo.vacay.ai",
            PUBLIC_REMOTE_BROWSER_URL="https://demo.vacay.ai/remote-browser/vnc.html",
        ),
        raising=False,
    )

    async def fake_checkout_flow(page, traveler, skip_fill=False):
        page.url = "https://www.trip.com/flights/passenger?booking=remote-reconnect"

    monkeypatch.setattr(runner, "_trip_select_offer_on_results", AsyncMock())
    monkeypatch.setattr(runner, "_trip_checkout_flow", fake_checkout_flow)
    monkeypatch.setattr(
        "backend.services.automation.playwright_checkout.browser_takeover_service",
        SimpleNamespace(
            enabled=True,
            create_takeover_url=AsyncMock(
                return_value="https://demo.vacay.ai/browser?token=reconnected"
            ),
        ),
        raising=False,
    )

    offer = {
        "id": "offer_remote_reconnect",
        "title": "Remote Reconnect Flight",
        "provider": "trip.com",
        "deeplink": "",
        "handoff_mode": "live_session_only",
        "results_page_url": fake_page.url,
        "live_session_id": "lost-session-id",
        "requires_live_session": True,
        "card_selector": "[data-testid='u-flight-card-1']",
    }

    result = asyncio.run(
        runner.checkout_to_confirmation(
            offer,
            traveler={},
            headless=False,
            skip_fill=True,
        )
    )

    assert result["status"] == "needs_user_input"
    assert result["handoff_channel"] == "remote_browser"
    assert result["confirmation_url"] == "https://demo.vacay.ai/browser?token=reconnected"
    assert fake_async_playwright.chromium.cdp_endpoint == "http://browser-worker:9222"

    for session_id in list(live_booking_sessions._sessions.keys()):
        asyncio.run(live_booking_sessions.close(session_id))
