"""browser-use powered discovery worker.

This module is intentionally lightweight: it defines a stable interface for the
agent, while allowing you to swap in real provider automation incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import inspect
import json
import re
from typing import Any
from urllib.parse import quote
import logging

from backend.config import settings
from backend.services.automation.live_booking_sessions import live_booking_sessions


class _LLMProviderShim:
    """Adapter to provide provider/model attrs expected by browser-use."""

    def __init__(self, llm: Any, provider: str, model: str):
        self._llm = llm
        self.provider = provider
        self.model = model
        self.model_name = model

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)


def build_browser_use_llm(*, temperature: float = 0) -> _LLMProviderShim:
    """Build the LLM wrapper expected by browser-use.

    The browser automation path must use the same provider choice as the rest of
    the agent graph, including fallback from DashScope to Gemini when only one
    provider is configured.
    """
    from backend.llm import get_agent_llm, resolve_agent_llm_config

    config = resolve_agent_llm_config(role="browser_use")
    llm = get_agent_llm(role="browser_use", temperature=temperature)
    return _LLMProviderShim(llm, config.provider, config.model)


@dataclass
class BookingQuery:
    booking_type: str
    origin: str
    destination: str
    departure_date: str
    return_date: str
    adults: int
    budget_limit: float
    provider_hint: str
    max_results: int
    origin_code: str = ""
    origin_city_code: str = ""
    destination_code: str = ""
    destination_city_code: str = ""
    trip_type: str = ""
    cabin: str = ""


class BrowserUseWorker:
    """Search worker that can be backed by browser-use.

    For local development, non-trip providers can still use mock fallbacks.
    For trip.com, strict mode can disable mock fallbacks.
    """

    def __init__(self):
        self.last_error: str = ""
        self.last_raw_text: str = ""

    async def search_offers(self, query: BookingQuery) -> list[dict[str, Any]]:
        """Return normalized offer objects.

        Each item contains: id, title, price, currency, provider, deeplink.
        """
        self.last_error = ""
        self.last_raw_text = ""
        provider = (query.provider_hint or "").strip().lower()
        is_trip = "trip" in provider
        if is_trip:
            try:
                offers = await asyncio.wait_for(self._search_with_playwright(query), timeout=90)
            except asyncio.TimeoutError:
                self.last_error = "playwright search timed out"
                _log = logging.getLogger(__name__)
                _log.warning(">>> PLAYWRIGHT timeout for trip.com search")
                offers = []
            if offers:
                return offers[: query.max_results]
            if settings.BOOKING_STRICT_REAL_TRIP:
                if not self.last_error:
                    self.last_error = "playwright returned no trip.com offers."
                return []

        offers = await self._search_with_browser_use(query)
        if offers:
            return offers[: query.max_results]
        if is_trip and settings.BOOKING_STRICT_REAL_TRIP:
            # Strict mode: for trip.com we must return real results only.
            if not self.last_error:
                self.last_error = "browser-use returned no parsable trip.com offer results."
            return []

        return self._mock_results(query)

    async def _search_with_browser_use(self, query: BookingQuery) -> list[dict[str, Any]]:
        """Try real browser-use discovery.

        This method is defensive against browser-use API changes across versions.
        """
        try:
            import browser_use  # type: ignore
        except Exception as exc:
            self.last_error = f"browser_use import failed: {exc}"
            return []

        Agent = getattr(browser_use, "Agent", None)
        if Agent is None:
            self.last_error = "browser_use.Agent not found in installed browser_use package."
            return []

        task_prompt = self._build_task_prompt(query)

        agent_kwargs: dict[str, Any] = {"task": task_prompt}
        try:
            init_sig = inspect.signature(Agent)
            if "llm" in init_sig.parameters:
                # Build a LangChain-compatible LLM for browser-use.
                agent_kwargs["llm"] = build_browser_use_llm(temperature=0)
        except Exception:
            # If signature introspection fails, keep minimal kwargs.
            pass

        try:
            agent = Agent(**agent_kwargs)
        except Exception as exc:
            self.last_error = f"browser_use.Agent init failed: {exc}"
            return []

        run_result: Any = None
        try:
            run_fn = getattr(agent, "run", None)
            if run_fn is None:
                self.last_error = "browser_use Agent has no run() method."
                return []

            run_sig = inspect.signature(run_fn)
            run_kwargs: dict[str, Any] = {}
            if "max_steps" in run_sig.parameters:
                run_kwargs["max_steps"] = 20

            run_result = await run_fn(**run_kwargs)
        except Exception as exc:
            self.last_error = f"browser_use run failed: {exc}"
            return []

        raw_text = self._extract_result_text(run_result)
        self.last_raw_text = raw_text
        parsed = self._parse_offers_json(raw_text)
        if not parsed:
            self.last_error = "browser_use returned output, but no valid JSON offers were parsed."
            _log = logging.getLogger(__name__)
            snippet = (raw_text or "").strip().replace("\n", " ")[:500]
            _log.info(">>> BROWSER_USE raw_output_snippet=%s", snippet)
        return self._normalize_offers(parsed, query)

    async def _search_with_playwright(self, query: BookingQuery) -> list[dict[str, Any]]:
        """Best-effort Trip.com scraping with Playwright.

        Returns normalized offers or [] on failure.
        """
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            self.last_error = f"playwright import failed: {exc}"
            return []

        urls = self._build_trip_search_urls(query)
        if not urls:
            self.last_error = "playwright search url build failed"
            return []

        offers: list[dict[str, Any]] = []
        _log = logging.getLogger(__name__)
        playwright_factory = async_playwright()
        if hasattr(playwright_factory, "start"):
            playwright = await playwright_factory.start()
        else:
            playwright = playwright_factory

        remote_cdp_url = str(getattr(settings, "REMOTE_BROWSER_CDP_URL", "") or "").strip()
        if remote_cdp_url:
            browser = await playwright.chromium.connect_over_cdp(remote_cdp_url)
            existing_contexts = list(getattr(browser, "contexts", []) or [])
            if existing_contexts and getattr(existing_contexts[0], "pages", None):
                page = existing_contexts[0].pages[0]
            elif existing_contexts and hasattr(existing_contexts[0], "new_page"):
                page = await existing_contexts[0].new_page()
            else:
                page = await browser.new_page()
        else:
            browser = await playwright.chromium.launch(headless=False, timeout=30000)
            page = await browser.new_page()
        session = await live_booking_sessions.register(
            provider="trip.com",
            playwright=playwright,
            browser=browser,
            page=page,
            query_summary=f"{query.origin}->{query.destination} {query.departure_date}",
        )
        try:
            for url in urls:
                try:
                    _log.info(">>> PLAYWRIGHT goto %s", url)
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception:
                    _log.warning(">>> PLAYWRIGHT goto failed for %s", url)
                    continue

                await self._save_trip_debug(page, "after_goto")

                try:
                    title = await page.title()
                except Exception:
                    title = ""
                if "404" in (title or ""):
                    continue

                is_results_url = "showfarefirst" in page.url
                is_results_title = "Flights from" in (title or "")
                if not is_results_url and not is_results_title:
                    try:
                        await asyncio.wait_for(
                            self._try_trigger_trip_search(page, query),
                            timeout=25,
                        )
                    except asyncio.TimeoutError:
                        _log.warning(">>> PLAYWRIGHT search trigger timed out")

                    await self._save_trip_debug(page, "after_search_trigger")

                try:
                    await asyncio.wait_for(self._wait_for_trip_results(page), timeout=25)
                except asyncio.TimeoutError:
                    _log.warning(">>> PLAYWRIGHT wait for results timed out")

                await self._save_trip_debug(page, "after_wait_results")

                if await self._is_trip_homepage(page):
                    self.last_error = "trip.com stayed on homepage after search"
                    await self._save_trip_debug(page)
                    continue

                offers = await self._scrape_trip_cards(page, query)
                if offers:
                    for item in offers:
                        item.setdefault("live_session_id", session.session_id)
                    return offers
                await self._save_trip_debug(page, "no_offers")
        except Exception:
            await live_booking_sessions.close(session.session_id)
            raise

        await live_booking_sessions.close(session.session_id)

        if not self.last_error:
            self.last_error = "playwright could not locate flight cards on trip.com"
        return []

    def _build_trip_search_urls(self, query: BookingQuery) -> list[str]:
        origin_raw = (query.origin or "").strip()
        dest_raw = (query.destination or "").strip()
        origin_code = (query.origin_code or "").strip() or self._extract_explicit_iata_code(origin_raw)
        dest_code = (query.destination_code or "").strip() or self._extract_explicit_iata_code(dest_raw)
        origin_city = (query.origin_city_code or "").strip()
        dest_city = (query.destination_city_code or "").strip()
        origin_query = quote(origin_code or origin_raw)
        dest_query = quote(dest_code or dest_raw)
        origin_slug = quote((origin_code or origin_raw).lower().replace(" ", "-"))
        dest_slug = quote((dest_code or dest_raw).lower().replace(" ", "-"))
        date = query.departure_date
        trip_type = "rt" if query.return_date or query.trip_type == "round_trip" else "ow"
        quantity = max(int(query.adults), 1)
        if not origin_raw or not dest_raw or not date:
            return []

        # Best-effort URL patterns (Trip.com changes these often).
        return [
            "https://www.trip.com/flights/showfarefirst/?"
            f"dcity={origin_city or origin_query}&"
            f"acity={dest_city or dest_query}&"
            f"ddate={date}&"
            f"triptype={trip_type}&class=y&quantity={quantity}&searchboxarg=t&nonstoponly=off&locale=en-XX&curr=USD"
            + (f"&rdate={query.return_date}" if query.return_date else "")
            + (f"&dairport={origin_code}" if origin_code else "")
            + (f"&aairport={dest_code}" if dest_code else ""),
            f"https://www.trip.com/flights/?triptype={'roundtrip' if trip_type == 'rt' else 'oneway'}&dcity={origin_query}&acity={dest_query}&date={date}"
            + (f"&returnDate={query.return_date}" if query.return_date else ""),
            f"https://www.trip.com/flights/{origin_slug}-to-{dest_slug}/?departuredate={date}&triptype={'roundtrip' if trip_type == 'rt' else 'oneway'}"
            + (f"&returndate={query.return_date}" if query.return_date else ""),
            f"https://www.trip.com/flights/{origin_slug}-to-{dest_slug}/?triptype={'roundtrip' if trip_type == 'rt' else 'oneway'}&departuredate={date}"
            + (f"&returndate={query.return_date}" if query.return_date else ""),
        ]

    def _extract_explicit_iata_code(self, value: str) -> str | None:
        if not value:
            return None
        match = re.search(r"\b([A-Z]{3})\b", value)
        return match.group(1) if match else None

    def _is_results_page(self, url: str) -> bool:
        lowered = (url or "").lower()
        if "/flights/passenger" in lowered:
            return False
        if "showfarefirst" in lowered:
            return True
        if "/flights/?" in lowered and "triptype" in lowered:
            return True
        return False

    async def _try_trigger_trip_search(self, page: Any, query: BookingQuery) -> None:
        try:
            if query.return_date:
                trip_type = "[data-testid='flightType_RT']"
            else:
                trip_type = "[data-testid='flightType_OW']"
            try:
                await page.click(trip_type)
            except Exception:
                pass

            if query.origin:
                origin_code = (query.origin_code or "").strip() or self._extract_explicit_iata_code(query.origin)
                await page.click("[data-testid='search_city_from0']")
                await page.fill("input[data-testid='search_city_from0']", query.origin)
                await page.wait_for_timeout(300)
                await self._select_poi_suggestion(page, origin_code)

            if query.destination:
                dest_code = (query.destination_code or "").strip() or self._extract_explicit_iata_code(query.destination)
                await page.click("[data-testid='search_city_to0']")
                await page.fill("input[data-testid='search_city_to0']", query.destination)
                await page.wait_for_timeout(300)
                await self._select_poi_suggestion(page, dest_code)

            if query.departure_date:
                current_date = None
                try:
                    current_date = await page.get_attribute(
                        "[data-testid='search_date_depart0']",
                        "data-date",
                    )
                except Exception:
                    current_date = None
                if current_date != query.departure_date:
                    await page.click("[data-testid='search_date_depart0']")
                    await self._click_calendar_date(page, query.departure_date)

            if query.return_date:
                await page.click("[data-testid='search_date_return0']")
                await self._click_calendar_date(page, query.return_date)

            try:
                await page.click("button:has-text('Confirm departure date')")
            except Exception:
                pass
            try:
                await page.click("button:has-text('Confirm dates')")
            except Exception:
                pass
            try:
                await page.click("button:has-text('Done')")
            except Exception:
                pass
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

            if not await self._click_search_button(page):
                return
            await page.wait_for_load_state("domcontentloaded", timeout=45000)
        except Exception:
            return

    async def _select_poi_suggestion(self, page: Any, airport_code: str | None) -> None:
        try:
            await page.wait_for_selector("[data-testid='search_result_box']", timeout=3000)
            if airport_code:
                try:
                    await page.click(f"[data-testid='search_result_box'] li:has-text('{airport_code}')")
                    await page.wait_for_timeout(200)
                    return
                except Exception:
                    pass
            await page.click("[data-testid='search_result_box'] li[role='listitem']")
            await page.wait_for_timeout(200)
        except Exception:
            try:
                await page.keyboard.press("Enter")
            except Exception:
                return

    async def _click_search_button(self, page: Any) -> bool:
        selectors = [
            "[data-testid='search_btn']",
            ".nh_sf-searhBtn",
            "[aria-label='Search']",
        ]
        for sel in selectors:
            try:
                button = await page.query_selector(sel)
                if button:
                    try:
                        await button.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    await button.click()
                    return True
            except Exception:
                continue
        try:
            await page.evaluate(
                """
                () => {
                    const btn = document.querySelector("[data-testid='search_btn']") ||
                        document.querySelector("[aria-label='Search']");
                    if (btn) btn.click();
                }
                """
            )
            return True
        except Exception:
            return False
        return False

    async def _click_calendar_date(self, page: Any, date_str: str) -> None:
        next_selectors = [
            "button[aria-label='Next month']",
            "[data-testid='calendar_next']",
            ".calendar-next",
            ".m-calendar__next",
            ".flight-calendar-next",
            ".date-picker-next",
        ]
        for _ in range(12):
            try:
                await page.wait_for_selector(f"[data-date='{date_str}']", timeout=1500)
                await page.click(f"[data-date='{date_str}']")
                await page.wait_for_timeout(200)
                return
            except Exception:
                pass
            moved = False
            for sel in next_selectors:
                try:
                    button = await page.query_selector(sel)
                    if button:
                        await button.click()
                        moved = True
                        await page.wait_for_timeout(200)
                        break
                except Exception:
                    continue
            if not moved:
                return

    async def _is_trip_homepage(self, page: Any) -> bool:
        try:
            page_name = await page.evaluate(
                """
                () => {
                    const state = window.__APP_INITIAL_STATE__ || {};
                    return state.pageName || "";
                }
                """
            )
            return str(page_name) == "new-index"
        except Exception:
            return False

    async def _wait_for_trip_results(self, page: Any) -> None:
        selectors = [
            "[data-testid^='u-flight-card-']",
            "[data-testid^='flight_price_']",
            "div.result-item.J_FlightItem",
        ]
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=12000)
                return
            except Exception:
                continue
        try:
            await page.wait_for_timeout(3000)
        except Exception:
            return

    async def _scrape_trip_cards(self, page: Any, query: BookingQuery) -> list[dict[str, Any]]:
        selectors = [
            "[data-testid^='u-flight-card-']",
            "div.result-item.J_FlightItem",
            "[data-flight-id]",
        ]

        cards = []
        cards_selector = ""
        for sel in selectors:
            try:
                found = await page.query_selector_all(sel)
            except Exception:
                found = []
            if found:
                cards = found
                cards_selector = sel
                break

        if not cards:
            self.last_error = "playwright found no flight cards with known selectors"
            return []

        offers: list[dict[str, Any]] = []
        try:
            page_url = page.url
        except Exception:
            page_url = ""
        for idx, card in enumerate(cards, start=1):
            card_selector = ""
            try:
                data_testid = await card.get_attribute("data-testid")
                if data_testid:
                    card_selector = f"[data-testid='{data_testid}']"
            except Exception:
                card_selector = ""
            if not card_selector and cards_selector:
                card_selector = f"{cards_selector}:nth-of-type({idx})"
            if not card_selector:
                try:
                    card_id = await card.get_attribute("id")
                    if card_id:
                        card_selector = f"#{card_id}"
                except Exception:
                    card_selector = ""
            try:
                text = (await card.inner_text()) if card else ""
            except Exception:
                text = ""

            airline = ""
            dep_code = ""
            arr_code = ""
            try:
                airline_node = await card.query_selector("[data-testid='flights-name']")
                if airline_node:
                    airline = (await airline_node.inner_text()).strip()
            except Exception:
                airline = ""

            try:
                dep_node = await card.query_selector(".flight-info-stop__code_e162")
                if dep_node:
                    dep_code = (await dep_node.inner_text()).strip()
                arr_nodes = await card.query_selector_all(".flight-info-stop__code_e162")
                if arr_nodes and len(arr_nodes) > 1:
                    arr_code = (await arr_nodes[-1].inner_text()).strip()
            except Exception:
                dep_code = dep_code or ""
                arr_code = arr_code or ""

            title = self._extract_title_from_text(text, query, idx)
            if airline and dep_code and arr_code:
                title = f"{airline} {dep_code} -> {arr_code}"

            price = None
            currency = None
            try:
                price_node = await card.query_selector("[data-testid^='flight_price_']")
                if price_node:
                    price_text = (await price_node.inner_text()).strip()
                    price, currency = self._extract_price_from_text(price_text)
            except Exception:
                price = None
                currency = None
            if price is None:
                price, currency = self._extract_price_from_text(text)

            deeplink = ""
            try:
                link = await card.query_selector("a")
                if link:
                    href = await link.get_attribute("href")
                    if href:
                        deeplink = href if href.startswith("http") else f"https://www.trip.com{href}"
            except Exception:
                deeplink = ""

            results_page_url = page_url if self._is_results_page(page_url) else ""
            is_true_deeplink = bool(deeplink) and not self._is_results_page(deeplink)
            if not is_true_deeplink:
                deeplink = ""

            if price is not None:
                offers.append(
                    {
                        "id": f"offer_{idx}",
                        "title": title,
                        "price": price,
                        "currency": currency or "USD",
                        "provider": "trip.com",
                        "deeplink": deeplink,
                        "card_selector": card_selector,
                        "results_page_url": results_page_url,
                        "handoff_mode": "deeplink" if is_true_deeplink else "live_session_only",
                        "requires_live_session": not is_true_deeplink,
                        "departure_date": query.departure_date,
                        "return_date": query.return_date,
                    }
                )

            if len(offers) >= query.max_results:
                break

        if not offers:
            self.last_error = "playwright parsed cards but no usable offers (missing price/deeplink)"
        return offers

    async def _save_trip_debug(self, page: Any, label: str = "") -> None:
        import os
        from datetime import datetime

        debug_dir = "backend/data/booking_debug"
        os.makedirs(debug_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = f"_{label}" if label else ""
        try:
            await page.screenshot(path=f"{debug_dir}/trip_search_{stamp}{safe_label}.png", full_page=True)
            html = await page.content()
            with open(f"{debug_dir}/trip_search_{stamp}{safe_label}.html", "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            return

    def _extract_price_from_text(self, text: str) -> tuple[float | None, str | None]:
        if not text:
            return None, None
        match = re.search(
            r"(USD|US\$|SGD|S\$|CNY|RMB|JPY|HKD)?\s?([0-9]{2,6}(?:,[0-9]{3})?)",
            text,
        )
        if not match:
            return None, None
        currency = (match.group(1) or "").upper()
        if currency in {"US$", "USD"}:
            currency = "USD"
        elif currency in {"S$", "SGD"}:
            currency = "SGD"
        elif currency in {"CNY", "RMB"}:
            currency = "CNY"
        try:
            price = float(match.group(2).replace(",", ""))
        except Exception:
            price = None
        return price, currency

    def _extract_title_from_text(self, text: str, query: BookingQuery, idx: int) -> str:
        if not text:
            return f"{query.origin} to {query.destination} option {idx}"
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines[0] if lines else f"{query.origin} to {query.destination} option {idx}"

    def _build_task_prompt(self, query: BookingQuery) -> str:
        provider = query.provider_hint or "trip.com"
        if "trip" in provider.lower():
            return self._build_trip_prompt(query)

        return (
            "You are a booking discovery assistant. "
            f"Find {query.booking_type} options on {provider}. "
            f"Origin: {query.origin}. Destination: {query.destination}. "
            f"Departure date: {query.departure_date}. "
            f"Return date: {query.return_date or 'N/A'}. "
            f"Adults: {query.adults}. Budget limit: {query.budget_limit or 'none'}. "
            f"Return exactly {query.max_results} or fewer options. "
            "Output STRICT JSON only as an array of objects with keys: "
            "id, title, price, currency, provider, deeplink, departure_date, return_date. "
            "Do not include markdown or explanation text."
        )

    def _build_trip_prompt(self, query: BookingQuery) -> str:
        """Trip.com-specific extraction prompt for higher consistency."""
        return (
            "Open https://www.trip.com and search booking options with the exact constraints below. "
            f"Booking type: {query.booking_type}. "
            f"Origin: {query.origin}. Destination: {query.destination}. "
            f"Departure date: {query.departure_date}. Return date: {query.return_date or 'N/A'}. "
            f"Adults: {query.adults}. Budget limit: {query.budget_limit or 'none'}. "
            "Prefer options with clear cancellation policy and official provider pages. "
            "Return STRICT JSON only, no markdown, no comments. "
            "JSON must be an array of objects with fields: "
            "id, title, price, currency, provider, deeplink, departure_date, return_date. "
            f"Return at most {query.max_results} items. "
            "Each deeplink must be a real trip.com URL for the specific offer, not homepage. "
            "If you cannot find valid trip.com deeplinks, return an empty array []."
        )

    def _extract_result_text(self, run_result: Any) -> str:
        if run_result is None:
            return ""

        # Common browser-use result representations.
        if isinstance(run_result, str):
            return run_result

        for attr in ("final_result", "result", "output", "text"):
            value = getattr(run_result, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if isinstance(value, str) and value.strip():
                return value

        return str(run_result)

    def _parse_offers_json(self, raw_text: str) -> list[dict[str, Any]]:
        if not raw_text:
            return []

        text = raw_text.strip()
        # Try direct JSON first.
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            if isinstance(data, dict):
                offers = data.get("offers", [])
                return [x for x in offers if isinstance(x, dict)]
        except Exception:
            pass

        # Fallback: extract first JSON array block.
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []

        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except Exception:
            return []

        return []

    def _normalize_offers(
        self,
        offers: list[dict[str, Any]],
        query: BookingQuery,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(offers, start=1):
            title = str(item.get("title") or f"{query.origin} to {query.destination} option {idx}")

            raw_price = item.get("price", 0)
            try:
                price = float(raw_price)
            except Exception:
                price = 0.0

            offer = {
                "id": str(item.get("id") or f"offer_{idx}"),
                "title": title,
                "price": price,
                "currency": str(item.get("currency") or "USD"),
                "provider": str(item.get("provider") or query.provider_hint or "trip.com"),
                "deeplink": str(item.get("deeplink") or ""),
                "departure_date": str(item.get("departure_date") or query.departure_date),
                "return_date": str(item.get("return_date") or query.return_date),
            }

            # Must have deeplink to be actionable.
            if offer["deeplink"].startswith("http"):
                normalized.append(offer)

        return normalized

    def _mock_results(self, query: BookingQuery) -> list[dict[str, Any]]:
        """Deterministic fallback so the booking flow can be tested end-to-end."""
        provider = query.provider_hint or "trip.com"
        return [
            {
                "id": f"offer_{i+1}",
                "title": f"{query.origin} to {query.destination} option {i+1}",
                "price": 120 + i * 35,
                "currency": "USD",
                "provider": provider,
                "deeplink": f"https://{provider}/demo-offer-{i+1}",
                "departure_date": query.departure_date,
                "return_date": query.return_date,
            }
            for i in range(min(query.max_results, 5))
        ]


browser_use_worker = BrowserUseWorker()
