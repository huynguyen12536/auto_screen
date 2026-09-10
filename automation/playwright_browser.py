"""Playwright browser controller.

Works headless, so screenshots and interactions still work when no
desktop window is visible (including minimized tabs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("playwright")


class PlaywrightBrowserController:
    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        navigation_timeout_ms: float = 120_000,
        ready_selector: str = ".mainContainer",
        ready_timeout_ms: float = 120_000,
    ) -> None:
        self._headless = headless
        self._viewport = {"width": viewport_width, "height": viewport_height}
        self._navigation_timeout_ms = int(navigation_timeout_ms)
        self._ready_selector = ready_selector
        self._ready_timeout_ms = int(ready_timeout_ms)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Playwright page is not ready. Call navigate() first.")
        return self._page

    def start(self) -> None:
        if self._browser is not None:
            return
        logger.info(
            "Starting Playwright Chromium | headless=%s viewport=%sx%s",
            self._headless,
            self._viewport["width"],
            self._viewport["height"],
        )
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context(viewport=self._viewport)
        self._page = self._context.new_page()
        self._page.set_default_timeout(self._navigation_timeout_ms)

    def navigate(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        ready_selector: str | None = None,
    ) -> None:
        if not url:
            raise ValueError("TARGET_URL is empty")
        self.start()
        selector = ready_selector or self._ready_selector
        logger.info(
            "Navigating | url=%s wait_until=%s ready_selector=%s",
            url,
            wait_until,
            selector,
        )
        try:
            response = self.page.goto(
                url,
                wait_until=wait_until,
                timeout=self._navigation_timeout_ms,
            )
            status = response.status if response is not None else "No response"
            logger.info("HTTP status | status=%s", status)

            # Prefer rendered UI over networkidle (site may never go idle).
            self.wait_for_ready(selector)
            logger.info(
                "Website ready | title=%s selector=%s", self.page.title(), selector
            )
        except PlaywrightTimeoutError as exc:
            logger.error(
                "Website load timeout | url=%s selector=%s error=%s",
                url,
                selector,
                exc,
            )
            raise

    def wait_for_ready(self, selector: str | None = None) -> None:
        target = selector or self._ready_selector
        if not target:
            return
        logger.info(
            "Waiting for visible element | selector=%s timeout_ms=%s",
            target,
            self._ready_timeout_ms,
        )
        self.page.locator(target).first.wait_for(
            state="visible",
            timeout=self._ready_timeout_ms,
        )

    def screenshot(
        self,
        output_path: Path,
        full_page: bool = True,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(output_path), full_page=full_page)
        logger.info("Playwright screenshot saved | path=%s", output_path)
        return output_path

    def fill(self, selector: str, value: str) -> None:
        self.page.fill(selector, value)

    def click(self, selector: str) -> None:
        self.page.click(selector)

    def wait(self, seconds: float) -> None:
        sleep(seconds)

    def close(self) -> None:
        for closer in (
            getattr(self._context, "close", None),
            getattr(self._browser, "close", None),
            getattr(self._playwright, "stop", None),
        ):
            if closer is None:
                continue
            try:
                closer()
            except Exception:
                logger.debug("Playwright cleanup failed", exc_info=True)
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        logger.info("Playwright browser closed")

    def __enter__(self) -> PlaywrightBrowserController:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
