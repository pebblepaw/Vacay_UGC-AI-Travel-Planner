"""Playwright checkout runner.

Moves from selected offer deeplink to a pre-payment confirmation page.
Never clicks final payment.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

from backend.services.browser_takeover import browser_takeover_service
from backend.services.automation.live_booking_sessions import live_booking_sessions
from backend.services.automation.remote_cdp import resolve_remote_cdp_url
from backend.config import settings


class PlaywrightCheckoutRunner:
    """Automates deterministic checkout steps with Playwright."""

    def __init__(self, artifacts_dir: str = "backend/data/booking_artifacts"):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def checkout_to_confirmation(
        self,
        offer: dict[str, Any],
        traveler: dict[str, str],
        headless: bool = True,
        skip_fill: bool = False,
    ) -> dict[str, Any]:
        """Open checkout and fill traveler details until confirmation page.

        Returns screenshot path and status metadata.
        """
        live_session_id = str(offer.get("live_session_id") or "").strip()
        live_session = await live_booking_sessions.get(live_session_id)
        requires_live_session = bool(offer.get("requires_live_session"))

        if requires_live_session and live_session is None:
            live_session = await self._reconnect_remote_live_session(offer)
            if live_session is not None:
                live_session_id = live_session.session_id
        if requires_live_session and live_session is None:
            return {
                "status": "failed",
                "reason": (
                    "This fare only had a live session handle from the Trip.com results page. "
                    "The live session is no longer available, so I cannot reopen the exact booking page."
                ),
                "confirmation_url": str(offer.get("results_page_url") or ""),
                "screenshot": "",
            }

        async_playwright = None
        if live_session is None:
            try:
                from playwright.async_api import async_playwright as imported_async_playwright
            except Exception as exc:
                return {
                    "status": "failed",
                    "reason": f"Playwright not installed: {exc}",
                    "confirmation_url": "",
                    "screenshot": "",
                }
            async_playwright = imported_async_playwright

        deeplink = offer.get("deeplink", "")
        if not deeplink:
            if live_session is None:
                return {
                    "status": "failed",
                    "reason": "Selected offer has no deeplink.",
                    "confirmation_url": str(offer.get("results_page_url") or ""),
                    "screenshot": "",
                }
        is_results_deeplink = self._is_results_page(deeplink)
        results_page_url = str(offer.get("results_page_url") or "")
        using_live_browser = live_session is not None
        browser = None

        if live_session is not None:
            page = live_session.page
        else:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                page = await browser.new_page()
                return await self._run_checkout_flow(
                    page=page,
                    browser=browser,
                    offer=offer,
                    traveler=traveler,
                    headless=headless,
                    skip_fill=skip_fill,
                    deeplink=deeplink,
                    is_results_deeplink=is_results_deeplink,
                    results_page_url=results_page_url,
                    using_live_browser=False,
                    live_session_id=live_session_id,
                )

        return await self._run_checkout_flow(
            page=page,
            browser=browser,
            offer=offer,
            traveler=traveler,
            headless=headless,
            skip_fill=skip_fill,
            deeplink=deeplink,
            is_results_deeplink=is_results_deeplink,
            results_page_url=results_page_url,
            using_live_browser=using_live_browser,
            live_session_id=live_session_id,
        )

    async def _reconnect_remote_live_session(self, offer: dict[str, Any]) -> Any | None:
        remote_cdp_url = str(getattr(settings, "REMOTE_BROWSER_CDP_URL", "") or "").strip()
        if not remote_cdp_url:
            return None
        remote_cdp_url = resolve_remote_cdp_url(remote_cdp_url)

        try:
            from playwright.async_api import async_playwright as imported_async_playwright
        except Exception:
            return None

        playwright_factory = imported_async_playwright()
        if hasattr(playwright_factory, "start"):
            playwright = await playwright_factory.start()
        else:
            playwright = playwright_factory

        browser = None
        try:
            browser = await playwright.chromium.connect_over_cdp(remote_cdp_url)
            existing_contexts = list(getattr(browser, "contexts", []) or [])
            if existing_contexts and getattr(existing_contexts[0], "pages", None):
                page = existing_contexts[0].pages[0]
            elif existing_contexts and hasattr(existing_contexts[0], "new_page"):
                page = await existing_contexts[0].new_page()
            else:
                page = await browser.new_page()

            return await live_booking_sessions.register(
                provider=str(offer.get("provider") or "trip.com"),
                playwright=playwright,
                browser=browser,
                page=page,
                query_summary=str(
                    offer.get("title")
                    or offer.get("results_page_url")
                    or offer.get("deeplink")
                    or "trip.com live reconnect"
                ),
            )
        except Exception:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            stop = getattr(playwright, "stop", None)
            if callable(stop):
                await stop()
            return None

    async def _run_checkout_flow(
        self,
        *,
        page: Any,
        browser: Any,
        offer: dict[str, Any],
        traveler: dict[str, str],
        headless: bool,
        skip_fill: bool,
        deeplink: str,
        is_results_deeplink: bool,
        results_page_url: str,
        using_live_browser: bool,
        live_session_id: str,
    ) -> dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        before_path = self.artifacts_dir / f"checkout_before_{timestamp}.png"
        after_path = self.artifacts_dir / f"checkout_pre_payment_{timestamp}.png"

        try:
            try:
                await page.bring_to_front()
            except Exception:
                pass

            if deeplink and not is_results_deeplink:
                await page.goto(deeplink, wait_until="domcontentloaded", timeout=45000)
            elif results_page_url and page.url != results_page_url:
                await page.goto(results_page_url, wait_until="domcontentloaded", timeout=45000)

            await page.screenshot(path=str(before_path), full_page=True)

            provider = str(offer.get("provider") or "")
            if self._is_trip_provider(provider, deeplink or results_page_url):
                if self._is_results_page(page.url):
                    await self._trip_select_offer_on_results(page, offer)
                await self._trip_checkout_flow(page, traveler, skip_fill=skip_fill)
            else:
                await self._handle_cookie_banner(page)
                await self._progress_to_checkout_step(page)
                if not skip_fill:
                    await self._fill_traveler_form(page, traveler)

            await page.screenshot(path=str(after_path), full_page=True)

            if self._is_results_page(page.url):
                if await self._has_provider_verification_wall(page):
                    return {
                        "status": "needs_user_input",
                        "reason": (
                            "CAPTCHA encountered. Trip.com requires verification before checkout. "
                            "Open this page, complete the verification, then continue."
                        ),
                        "confirmation_url": page.url,
                        "current_browser_url": page.url,
                        "handoff_channel": "provider_verification",
                        "screenshot": str(after_path),
                        "artifacts": [str(before_path), str(after_path)],
                    }
                return {
                    "status": "failed",
                    "reason": "Still on search results page; checkout form not reached.",
                    "confirmation_url": page.url,
                    "screenshot": str(after_path),
                    "artifacts": [str(before_path), str(after_path)],
                }

            result_status = "needs_user_payment"
            result_reason = "Reached pre-payment stage. Final payment is intentionally not clicked."
            if skip_fill:
                result_status = "needs_user_input"
                result_reason = "Reached traveler info page. Please fill manually in the browser."

            result = {
                "status": result_status,
                "reason": result_reason,
                "confirmation_url": page.url,
                "current_browser_url": page.url,
                "screenshot": str(after_path),
                "artifacts": [str(before_path), str(after_path)],
            }
            if using_live_browser or not headless:
                direct_confirmation_url = str(page.url or "")
                direct_url_reusable = False
                if direct_confirmation_url and not self._is_results_page(direct_confirmation_url):
                    if self._is_trip_provider(provider, direct_confirmation_url):
                        direct_url_reusable = await self._can_reuse_direct_handoff_url(
                            direct_confirmation_url
                        )
                    else:
                        direct_url_reusable = True
                if direct_url_reusable:
                    result["handoff_channel"] = "direct_url"
                    if skip_fill:
                        result["reason"] = (
                            "Reached traveler info page on the provider site. "
                            "Continue there."
                        )
                    else:
                        result["reason"] = (
                            "Reached pre-payment stage on the provider site. "
                            "Review the fare and finish there."
                        )
                else:
                    result["handoff_channel"] = "live_browser"
                    if skip_fill:
                        result["reason"] = "Reached traveler info page in the live browser window. Continue there."
                    else:
                        result["reason"] = (
                            "Reached pre-payment stage in the live browser window. "
                            "Review and finish there. Final payment is intentionally not clicked."
                        )
                if result["handoff_channel"] != "direct_url" and live_session_id and browser_takeover_service.enabled:
                    result["handoff_channel"] = "remote_browser"
                    result["confirmation_url"] = await browser_takeover_service.create_takeover_url(
                        session_id=live_session_id,
                        workspace_id=str(offer.get("workspace_id") or "") or None,
                    )
                    if skip_fill:
                        result["reason"] = "Reached traveler info page in the hosted remote browser. Continue there."
                    else:
                        result["reason"] = (
                            "Reached pre-payment stage in the hosted remote browser. "
                            "Review the fare and finish there."
                        )
            return result
        finally:
            if browser is not None and headless:
                await browser.close()

    def _is_trip_provider(self, provider: str, deeplink: str) -> bool:
        haystack = f"{provider} {deeplink}".lower()
        return "trip.com" in haystack or re.search(r"(^|\.)trip\.com", haystack) is not None

    def _is_results_page(self, url: str) -> bool:
        lowered = (url or "").lower()
        if "/flights/passenger" in lowered:
            return False
        if "showfarefirst" in lowered:
            return True
        if "/flights/?" in lowered or "/flights/" in lowered and "triptype" in lowered:
            return True
        return False

    async def _can_reuse_direct_handoff_url(self, confirmation_url: str) -> bool:
        """Check whether a provider URL can be reopened outside the live session.

        Trip.com passenger links can look valid inside the live browser but still
        redirect fresh viewers to sign-in. Those must fall back to the hosted
        remote browser instead of being handed to the user as a dead end.
        """
        target_url = str(confirmation_url or "").strip()
        if not target_url or self._is_results_page(target_url):
            return False

        try:
            from playwright.async_api import async_playwright as imported_async_playwright
        except Exception:
            return False

        try:
            async with imported_async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(2500)
                    final_url = str(page.url or "")
                    lowered_url = final_url.lower()
                    if self._is_results_page(final_url):
                        return False
                    if "/account/signin" in lowered_url or "forcelogin" in lowered_url or "/signin" in lowered_url:
                        return False

                    page_text = ""
                    try:
                        page_text = (await page.locator("body").inner_text(timeout=5000) or "").lower()
                    except Exception:
                        page_text = ""

                    sign_in_markers = [
                        "sign in to trip.com",
                        "sign in/register",
                        "continue with email",
                        "continue with google",
                        "continue with apple",
                    ]
                    if any(marker in page_text for marker in sign_in_markers):
                        return False

                    if "/flights/passenger" in lowered_url:
                        return True
                    if any(marker in page_text for marker in ["passenger", "traveler", "payment"]):
                        return True
                    return True
                finally:
                    await browser.close()
        except Exception:
            return False

    async def _has_provider_verification_wall(self, page: Any) -> bool:
        """Detect provider security checks that require manual user action."""
        page_text = ""
        try:
            page_text = (await page.locator("body").inner_text(timeout=3000) or "").lower()
        except Exception:
            try:
                page_text = (await page.content() or "").lower()
            except Exception:
                page_text = ""

        markers = [
            "too many attempts",
            "complete the verification",
            "select icons in the correct order",
            "verification below",
            "captcha",
            "security verification",
            "verify you are human",
        ]
        return any(marker in page_text for marker in markers)

    async def _trip_handle_baggage(self, page: Any) -> None:
        """Select default baggage and continue if baggage step is shown."""
        try:
            await page.wait_for_timeout(800)
        except Exception:
            pass
        try:
            title = (await page.title()) or ""
        except Exception:
            title = ""

        text_markers = ["Baggage", "行李", "luggage"]
        is_baggage_step = any(marker.lower() in title.lower() for marker in text_markers)

        if not is_baggage_step:
            try:
                page_text = await page.content()
                is_baggage_step = any(marker.lower() in page_text.lower() for marker in text_markers)
            except Exception:
                is_baggage_step = False

        if not is_baggage_step:
            return

        try:
            radio = page.locator("input[type='radio']")
            if await radio.count() > 0:
                await radio.first.check(timeout=2000)
        except Exception:
            pass

        await self._click_first_available(
            page,
            [
                ("role", "Continue"),
                ("role", "Next"),
                ("role", "Confirm"),
                ("role", "下一步"),
                ("role", "继续"),
                ("role", "确认"),
                ("css", "button:has-text('Continue')"),
                ("css", "button:has-text('Confirm')"),
            ],
        )
        await page.wait_for_timeout(1200)

    async def _trip_select_offer_on_results(self, page: Any, offer: dict[str, Any]) -> None:
        """Select a specific offer card on Trip.com results page."""
        selector = offer.get("card_selector") or ""
        if selector:
            try:
                card = page.locator(selector)
                if await card.count() > 0:
                    await card.first.scroll_into_view_if_needed()
                    btn = card.locator(
                        "button:has-text('Select'), a:has-text('Select'), button:has-text('Book'), "
                        "button:has-text('Continue'), button:has-text('立即预订'), button:has-text('预订')"
                    )
                    if await btn.count() > 0:
                        await btn.first.click(timeout=3000)
                        await self._wait_for_checkout_start(page)
                        return
            except Exception:
                pass

        offer_id = str(offer.get("id") or "")
        index_match = re.search(r"offer_(\d+)", offer_id)
        target_index = int(index_match.group(1)) - 1 if index_match else 0
        selectors = [
            "button:has-text('Select')",
            "a:has-text('Select')",
            "button:has-text('Book')",
        ]
        for sel in selectors:
            try:
                btns = page.locator(sel)
                if await btns.count() > 0:
                    target = btns.nth(target_index if target_index >= 0 else 0)
                    await target.scroll_into_view_if_needed()
                    await target.click(timeout=3000)
                    await self._wait_for_checkout_start(page)
                    return
            except Exception:
                continue

    async def _wait_for_checkout_start(self, page: Any) -> None:
        """Wait briefly for checkout form to appear or URL to change."""
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        selectors = [
            "input[name*='name']",
            "input[name*='passenger']",
            "input[name*='contact']",
            "input[placeholder*='Name']",
            "input[placeholder*='姓名']",
        ]
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                return
            except Exception:
                continue
        await page.wait_for_timeout(1200)

    async def _trip_checkout_flow(
        self, page: Any, traveler: dict[str, str], skip_fill: bool = False
    ) -> None:
        """Trip.com-specific pre-payment automation.

        This flow intentionally stops before payment submission.
        """
        await self._handle_cookie_banner(page)

        # Trip pages often lazy-render; wait briefly for CTA hydration.
        await page.wait_for_timeout(1500)

        # Step 1: enter booking flow.
        await self._click_first_available(
            page,
            [
                ("role", "Book now"),
                ("role", "Select"),
                ("role", "Reserve"),
                ("role", "Continue"),
                ("role", "Book"),
                ("role", "立即预订"),
                ("role", "预订"),
                ("css", "button[data-testid*='book']"),
                ("css", "button[data-testid*='select']"),
                ("css", "button[data-testid*='reserve']"),
                ("css", "button:has-text('Book')"),
                ("css", "button:has-text('Select')"),
            ],
        )
        await page.wait_for_timeout(1200)
        await self._trip_handle_results_fare_modal(page)

        # Step 1.5: handle baggage selection if present.
        await self._trip_handle_baggage(page)
        await self._trip_handle_results_fare_modal(page)

        # Step 2: fill traveler/contact details.
        if skip_fill:
            return
        await self._fill_traveler_form(page, traveler)

        # Step 3: proceed to confirmation step, but DO NOT click pay.
        await self._click_first_available(
            page,
            [
                ("role", "Continue"),
                ("role", "Next"),
                ("role", "Review"),
                ("role", "下一步"),
                ("role", "继续"),
                ("css", "button[data-testid*='continue']"),
                ("css", "button:has-text('Continue')"),
            ],
        )
        await page.wait_for_timeout(1500)

    async def _trip_handle_results_fare_modal(self, page: Any) -> bool:
        """Advance through Trip.com fare-selection dialogs shown on results pages."""
        if not self._is_results_page(page.url):
            return False

        await page.wait_for_timeout(1000)

        clicked_named_cta = await self._click_first_available(
            page,
            [
                ("css", "[role='dialog'] button:has-text('Continue')"),
                ("css", "[role='dialog'] button:has-text('Book')"),
                ("css", "[role='dialog'] button:has-text('Select')"),
                ("css", "[role='dialog'] button:has-text('Choose')"),
                ("css", "[role='dialog'] button:has-text('Confirm')"),
                ("css", "[role='dialog'] button:has-text('Next')"),
                ("css", "[role='dialog'] button:has-text('Reserve')"),
                ("css", "[role='dialog'] button:has-text('立即预订')"),
                ("css", "[role='dialog'] button:has-text('预订')"),
                ("css", "[role='dialog'] button:has-text('下一步')"),
                ("css", "[role='dialog'] button:has-text('继续')"),
                ("css", "[role='dialog'] button[class*='primary']"),
                ("css", "[aria-modal='true'] button[class*='primary']"),
                ("css", "div[class*='modal'] button[class*='primary']"),
                ("css", "div[class*='dialog'] button[class*='primary']"),
            ],
        )
        if clicked_named_cta:
            await self._wait_for_checkout_start(page)
            return not self._is_results_page(page.url)

        modal_selectors = [
            "[role='dialog']",
            "[aria-modal='true']",
            "div[class*='modal']",
            "div[class*='dialog']",
            "div[class*='drawer']",
        ]
        for selector in modal_selectors:
            try:
                modal = page.locator(selector)
                if await modal.count() <= 0:
                    continue
                buttons = modal.last.locator("button")
                count = await buttons.count()
                if count <= 0:
                    continue
                for index in range(count - 1, -1, -1):
                    button = buttons.nth(index)
                    try:
                        if not await button.is_visible():
                            continue
                    except Exception:
                        continue

                    try:
                        label = ((await button.inner_text()) or "").strip().lower()
                    except Exception:
                        label = ""
                    try:
                        aria_label = ((await button.get_attribute("aria-label")) or "").strip().lower()
                    except Exception:
                        aria_label = ""

                    if label in {"x", "close", "cancel"} or aria_label in {"close", "cancel"}:
                        continue

                    await button.click(timeout=2200)
                    await self._wait_for_checkout_start(page)
                    return not self._is_results_page(page.url)
            except Exception:
                continue
        return False

    async def _handle_cookie_banner(self, page: Any) -> None:
        """Best-effort cookie banner dismissal for common provider pages."""
        texts = [
            "Accept",
            "Accept all",
            "I agree",
            "Allow all",
            "同意",
            "全部接受",
        ]
        for text in texts:
            try:
                btn = page.get_by_role("button", name=text)
                if await btn.count() > 0:
                    await btn.first.click(timeout=1200)
                    return
            except Exception:
                continue

    async def _progress_to_checkout_step(self, page: Any) -> None:
        """Click common CTA buttons to move from offer page to traveler form.

        This is provider-agnostic and safe: all clicks are best effort.
        """
        ctas = [
            "Book",
            "Book now",
            "Continue",
            "Select",
            "Reserve",
            "下一步",
            "继续",
            "立即预订",
            "预订",
        ]
        for text in ctas:
            try:
                btn = page.get_by_role("button", name=text)
                if await btn.count() > 0:
                    await btn.first.click(timeout=1800)
                    await page.wait_for_timeout(1200)
            except Exception:
                continue

    async def _fill_traveler_form(self, page: Any, traveler: dict[str, str]) -> None:
        """Fill common traveler/contact fields until confirmation page.

        Uses multiple selectors per field to tolerate provider differences.
        """
        full_name = traveler.get("name", "").strip()
        first_name, last_name = self._split_name(full_name)

        await self._try_fill(
            page,
            [
                "input[name='fullName']",
                "input[name='contactName']",
                "input[name='passengerName']",
                "input[name='name']",
                "input[id*='name']",
                "input[placeholder*='Name']",
                "input[placeholder*='姓名']",
            ],
            full_name,
        )
        await self._try_fill(
            page,
            [
                "input[name*='first']",
                "input[name*='given']",
                "input[id*='first']",
                "input[id*='given']",
                "input[id*='first']",
                "input[placeholder*='First']",
                "input[placeholder*='Given']",
                "input[placeholder*='Given name']",
                "input[placeholder*='名']",
            ],
            first_name,
        )
        await self._try_fill(
            page,
            [
                "input[name*='last']",
                "input[name*='surname']",
                "input[id*='last']",
                "input[id*='surname']",
                "input[id*='last']",
                "input[placeholder*='Last']",
                "input[placeholder*='Family']",
                "input[placeholder*='Surname']",
                "input[placeholder*='姓']",
            ],
            last_name,
        )
        await self._try_fill(
            page,
            [
                "input[type='email']",
                "input[name='email']",
                "input[name='contactEmail']",
                "input[id*='email']",
                "input[placeholder*='Email']",
                "input[placeholder*='邮箱']",
            ],
            traveler.get("email", ""),
        )
        await self._try_fill(
            page,
            [
                "input[name*='contactName']",
                "input[id*='contactName']",
                "input[placeholder*='Contact name']",
                "input[placeholder*='contact name']",
                "input[placeholder*='联系人']",
            ],
            traveler.get("name", ""),
        )
        await self._try_fill(
            page,
            [
                "input[type='tel']",
                "input[name='phone']",
                "input[name='contactPhone']",
                "input[id*='phone']",
                "input[placeholder*='Phone']",
                "input[placeholder*='手机号']",
            ],
            traveler.get("phone", ""),
        )

        gender = traveler.get("gender", "").strip().lower()
        if gender:
            gender_texts = ["Male", "Female", "Other", "男", "女"]
            if gender.startswith("m"):
                gender_texts = ["Male", "男"]
            elif gender.startswith("f"):
                gender_texts = ["Female", "女"]
            await self._try_click_label(page, gender_texts)

        birth_date = traveler.get("birth_date", "").strip()
        if birth_date:
            await self._try_fill(
                page,
                [
                    "input[name*='birth']",
                    "input[id*='birth']",
                    "input[placeholder*='Birth']",
                    "input[placeholder*='Date of birth']",
                    "input[type='date']",
                ],
                birth_date,
            )
            year, month, day = self._split_date(birth_date)
            if year and month and day:
                await self._try_select_option(
                    page,
                    [
                        "select[name*='year']",
                        "select[id*='year']",
                        "select[aria-label*='Year']",
                    ],
                    year,
                )
                await self._try_select_option(
                    page,
                    [
                        "select[name*='month']",
                        "select[id*='month']",
                        "select[aria-label*='Month']",
                    ],
                    month,
                )
                await self._try_select_option(
                    page,
                    [
                        "select[name*='day']",
                        "select[id*='day']",
                        "select[aria-label*='Day']",
                    ],
                    day,
                )

        nationality = traveler.get("nationality", "").strip()
        if nationality:
            await self._try_select_option(
                page,
                [
                    "select[name*='national']",
                    "select[id*='national']",
                    "select[aria-label*='Nationality']",
                ],
                nationality,
            )
            await self._try_fill(
                page,
                [
                    "input[name*='national']",
                    "input[id*='national']",
                    "input[placeholder*='Nationality']",
                    "input[placeholder*='country/region']",
                    "input[placeholder*='Nationality']",
                    "input[placeholder*='国籍']",
                ],
                nationality,
            )

        doc_type = traveler.get("doc_type", "").strip()
        if doc_type:
            await self._try_select_option(
                page,
                [
                    "select[name*='documentType']",
                    "select[name*='docType']",
                    "select[id*='documentType']",
                    "select[aria-label*='Document']",
                    "select[aria-label*='证件']",
                ],
                doc_type,
            )
            await self._try_fill(
                page,
                [
                    "input[placeholder*='ID type']",
                    "input[placeholder*='Document type']",
                    "input[placeholder*='证件类型']",
                ],
                doc_type,
            )

        doc_number = traveler.get("doc_number", "").strip()
        if doc_number:
            await self._try_fill(
                page,
                [
                    "input[name*='passport']",
                    "input[name*='documentNumber']",
                    "input[name*='docNumber']",
                    "input[id*='passport']",
                    "input[id*='documentNumber']",
                    "input[placeholder*='ID number']",
                    "input[placeholder*='Passport']",
                    "input[placeholder*='Document']",
                    "input[placeholder*='证件']",
                ],
                doc_number,
            )

        doc_expiry = traveler.get("doc_expiry", "").strip()
        if doc_expiry:
            await self._try_fill(
                page,
                [
                    "input[name*='expiry']",
                    "input[id*='expiry']",
                    "input[placeholder*='Expiry']",
                    "input[placeholder*='Expiration']",
                    "input[type='date']",
                ],
                doc_expiry,
            )

        # One more non-destructive continue attempt.
        try:
            btn = page.get_by_role("button", name="Continue")
            if await btn.count() > 0:
                await btn.first.click(timeout=1800)
        except Exception:
            pass

    async def _click_first_available(self, page: Any, candidates: list[tuple[str, str]]) -> bool:
        """Click first matched button from ordered candidates.

        candidate tuple: (kind, value) where kind is 'role' or 'css'.
        """
        for kind, value in candidates:
            try:
                if kind == "role":
                    locator = page.get_by_role("button", name=value)
                else:
                    locator = page.locator(value)

                if await locator.count() > 0:
                    await locator.first.click(timeout=2200)
                    return True
            except Exception:
                continue
        return False

    async def _try_fill(self, page: Any, selectors: list[str], value: str) -> bool:
        if not value:
            return False
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.fill(value, timeout=1800)
                    return True
            except Exception:
                continue
        return False

    def _split_name(self, name: str) -> tuple[str, str]:
        if not name:
            return "", ""
        if re.search(r"[\u4e00-\u9fff]", name) and len(name) >= 2:
            return name[1:], name[0]
        parts = [p for p in name.split() if p]
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return name, name

    def _split_date(self, value: str) -> tuple[str, str, str]:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)
        if not match:
            return "", "", ""
        return match.group(1), str(int(match.group(2))), str(int(match.group(3)))

    async def _try_click_label(self, page: Any, labels: list[str]) -> bool:
        for label in labels:
            try:
                locator = page.get_by_label(label)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1800)
                    return True
            except Exception:
                pass
            try:
                locator = page.get_by_role("radio", name=label)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1800)
                    return True
            except Exception:
                pass
            try:
                locator = page.locator(f"button:has-text('{label}')")
                if await locator.count() > 0:
                    await locator.first.click(timeout=1800)
                    return True
            except Exception:
                continue
        return False

    async def _try_select_option(self, page: Any, selectors: list[str], value: str) -> bool:
        if not value:
            return False
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.select_option(label=value)
                    return True
            except Exception:
                pass
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1200)
                    option = page.locator(f"li:has-text('{value}'), div[role='option']:has-text('{value}')")
                    if await option.count() > 0:
                        await option.first.click(timeout=1200)
                        return True
            except Exception:
                continue
        return False


playwright_checkout_runner = PlaywrightCheckoutRunner()
