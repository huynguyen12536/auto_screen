"""Orchestrates opening the target page and capturing screenshots."""

from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from automation.browser import BrowserController, title_hint_from_url
from automation.keyboard import KeyboardController
from automation.mouse import MouseController
from automation.playwright_browser import PlaywrightBrowserController
from automation.window import WindowController
from feature.capture.screenshot import ScreenshotCapture
from utils.logger import get_logger
from utils.timing import sleep, sleep_human, wait_until

logger = get_logger("service")


class BrowserAutomationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._use_playwright = settings.browser.engine == "playwright"
        self._desktop_browser = BrowserController(
            browser_name=settings.browser.name,
            guest=settings.browser.guest,
        )
        self._playwright = PlaywrightBrowserController(
            headless=settings.browser.headless,
            viewport_width=settings.browser.viewport.width,
            viewport_height=settings.browser.viewport.height,
            navigation_timeout_ms=settings.timing.browser_start_timeout * 1000,
            ready_selector=settings.browser.ready_selector,
            ready_timeout_ms=settings.browser.ready_timeout_ms,
        )
        self._window = WindowController()
        self._keyboard = KeyboardController()
        self._mouse = MouseController()
        self._capture = ScreenshotCapture(
            output_dir=settings.capture.directory,
            image_format=settings.capture.format,
        )
        self._current_window = None

    def _action_pause(self) -> None:
        human = self._settings.timing.human
        if human.enabled:
            waited = sleep_human(
                min_time=human.min_time,
                max_time=human.max_time,
                mean=human.mean,
                std_dev=human.std_dev,
            )
            logger.debug("Human action pause | seconds=%.3f", waited)
            return
        sleep(self._settings.timing.action_delay)

    def open_target(self) -> None:
        url = self._settings.target_url
        if not url:
            raise ValueError("TARGET_URL is missing. Set it in the .env file.")
        logger.info(
            "Opening target | url=%s engine=%s headless=%s",
            url,
            self._settings.browser.engine,
            self._settings.browser.headless,
        )
        if self._use_playwright:
            self._playwright.navigate(
                url,
                wait_until="domcontentloaded",
                ready_selector=self._settings.browser.ready_selector,
            )
            sleep(self._settings.timing.page_load_delay)
            return

        existing_hwnds = self._window.list_hwnds()
        self._desktop_browser.navigate(url)
        hint = title_hint_from_url(url)
        wait_until(
            lambda: self._window.find_browser_window(hint, existing_hwnds) is not None,
            timeout=self._settings.timing.browser_start_timeout,
            message=f"Timed out waiting for browser window matching '{hint}'",
        )
        self._current_window = self._window.find_browser_window(hint, existing_hwnds)
        self._window.focus(self._current_window)
        self._window.maximize(self._current_window)
        sleep(self._settings.timing.page_load_delay)

    def login(self) -> None:
        if self._use_playwright:
            raise NotImplementedError(
                "Playwright login selectors are not configured yet."
            )
        username = self._settings.target_username
        password = self._settings.target_password
        if not username or not password:
            raise ValueError("TARGET_USERNAME and TARGET_PASSWORD must be set in .env")
        if self._current_window is None:
            hint = title_hint_from_url(self._settings.target_url)
            self._current_window = self._window.find_browser_window(hint)
        if self._current_window is None:
            raise ValueError("Browser window was not found for login")

        logger.info("Starting login")
        self._current_window = self._window.prepare_for_capture(
            self._current_window,
            timeout=self._settings.timing.browser_start_timeout,
        )
        bounds = self._window.get_bounds(self._current_window)
        login = self._settings.login
        interval = login.type_interval

        self._mouse.click_ratio(bounds, login.email.x_ratio, login.email.y_ratio)
        self._action_pause()
        self._keyboard.hotkey("ctrl", "a")
        self._keyboard.press("backspace")
        self._keyboard.type_text(username, interval=interval)
        self._action_pause()
        self._mouse.click_ratio(bounds, login.password.x_ratio, login.password.y_ratio)
        self._action_pause()
        self._keyboard.hotkey("ctrl", "a")
        self._keyboard.press("backspace")
        self._keyboard.type_text(password, interval=interval, secret=True)
        self._action_pause()
        self._mouse.click_ratio(bounds, login.submit.x_ratio, login.submit.y_ratio)
        self._action_pause()
        self._keyboard.press("enter")
        logger.info("Login submitted, waiting for page")
        sleep(login.submit_wait)

    def capture_current_page(self, stem: str | None = None) -> Path:
        hint = title_hint_from_url(self._settings.target_url) or "page"
        output_path = self._capture.build_output_path(stem or f"{hint}_page")

        if self._use_playwright:
            # Re-check ready state right before capture to avoid black frames.
            self._playwright.wait_for_ready(self._settings.browser.ready_selector)
            return self._playwright.screenshot(
                output_path,
                full_page=self._settings.capture.full_page,
            )

        if self._current_window is None:
            self._current_window = self._window.find_browser_window(hint)
        if self._current_window is None:
            raise ValueError("Browser window was not found for capture")
        self._current_window = self._window.prepare_for_capture(
            self._current_window,
            timeout=self._settings.timing.browser_start_timeout,
        )
        bounds = self._window.get_bounds(self._current_window)
        return self._capture.capture_window(bounds, output_path)

    def close(self) -> None:
        if self._use_playwright:
            self._playwright.close()
            return
        self._desktop_browser.close()
