import asyncio
import sys
import types
from unittest.mock import AsyncMock

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


class FakeChromium:
    def __init__(self, page: FakeSearchPage) -> None:
        self.page = page
        self.launch_kwargs = None

    async def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return FakeBrowser(self.page)


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
