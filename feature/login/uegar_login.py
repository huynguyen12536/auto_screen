"""uEgar login feature.

Fills credentials from settings and submits once.
On failure: log and raise LoginFailedError (no retry).
Never logs the password.

After login, waits until the Agendas palette button exists
(#repeaterPalette_ctl01_btnDiv) — that means the workspace shell is ready.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import Settings
from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("login")


class LoginFailedError(RuntimeError):
    """Raised when login fails. Callers must stop without retrying."""


class UegarLoginFeature:
    def __init__(
        self,
        page: Page,
        settings: Settings,
        action_pause: Callable[[], None] | None = None,
    ) -> None:
        self._page = page
        self._settings = settings
        self._login = settings.login
        self._action_pause = action_pause or (lambda: None)
        self._ready_timeout_ms = int(settings.browser.ready_timeout_ms)
        self._after = settings.login.after_login

    def run(self) -> None:
        username = self._settings.target_username
        password = self._settings.target_password
        if not username or not password:
            raise LoginFailedError(
                "TARGET_USERNAME and TARGET_PASSWORD must be set in .env"
            )

        selectors = self._login.selectors
        logger.info(
            "Starting login | username=%s",
            self._settings.masked_username(),
        )
        print(f"Logging in as {self._settings.masked_username()}...", flush=True)

        try:
            self._page.locator(selectors.username).wait_for(
                state="visible", timeout=30_000
            )
            self._page.locator(selectors.username).fill(username)
            self._action_pause()
            self._page.locator(selectors.password).fill(password)
            self._action_pause()
            self._page.locator(selectors.submit).click()
        except PlaywrightTimeoutError as exc:
            raise LoginFailedError(
                f"Login form not ready or not clickable: {exc}"
            ) from exc
        except Exception as exc:
            raise LoginFailedError(f"Login interaction failed: {exc}") from exc

        logger.info("Login submitted (single attempt, no retry)")
        print("Login submitted, waiting for result...", flush=True)
        self._wait_for_result()
        self._wait_for_workspace_ready()

    def _wait_for_result(self) -> None:
        """Wait until auth is accepted or login form leaves (may be white flash)."""
        deadline = max(float(self._login.submit_wait), self._ready_timeout_ms / 1000.0)
        poll = 0.5
        elapsed = 0.0
        while elapsed < deadline:
            if self._still_on_login_form() and self._detect_failure_message():
                message = self._failure_message() or "Login rejected by server"
                raise LoginFailedError(message)
            if self._auth_accepted():
                logger.info("Login accepted; waiting for Agendas palette")
                print("Login accepted, waiting for Agendas...", flush=True)
                return
            sleep(poll)
            elapsed += poll

        if self._still_on_login_form() and self._detect_failure_message():
            raise LoginFailedError(
                self._failure_message() or "Login rejected by server"
            )
        if self._still_on_login_form():
            raise LoginFailedError(
                "Login failed: still on login form after submit (no retry)"
            )
        logger.info("Login form left the page; waiting for Agendas palette")
        print("Login form gone, waiting for Agendas...", flush=True)

    def _wait_for_workspace_ready(self) -> None:
        """Wait until Agendas palette button exists (post-login ready signal)."""
        ready = self._after.ready_selector
        needle = self._after.url_contains
        timeout = self._ready_timeout_ms
        logger.info(
            "Waiting for post-login ready | selector=%s url_contains=%s timeout_ms=%s",
            ready,
            needle,
            timeout,
        )
        print(
            f"Waiting for post-login ready: {ready} (timeout {timeout}ms)...",
            flush=True,
        )
        try:
            if needle:
                self._page.wait_for_url(f"**/*{needle}*", timeout=timeout)
            self._page.locator(ready).first.wait_for(
                state="visible",
                timeout=timeout,
            )
            loading = self._after.loading_hidden_selector
            if loading and self._page.locator(loading).count() > 0:
                self._page.locator(loading).first.wait_for(
                    state="hidden",
                    timeout=timeout,
                )
        except PlaywrightTimeoutError as exc:
            url = ""
            try:
                url = self._page.url
            except Exception:
                pass
            raise LoginFailedError(
                f"Login may have succeeded but Agendas button never appeared "
                f"({ready}, url={url}): {exc}"
            ) from exc
        logger.info("Post-login ready (Agendas visible) | url=%s", self._page.url)
        print(f"Post-login ready: {self._page.url}", flush=True)

    def _still_on_login_form(self) -> bool:
        try:
            return self._page.locator(self._login.selectors.username).is_visible()
        except Exception:
            return False

    def _auth_accepted(self) -> bool:
        """True when server accepted credentials (page may still be blank)."""
        if self._after.ready_selector:
            try:
                if self._page.locator(self._after.ready_selector).first.is_visible():
                    return True
            except Exception:
                pass
        if self._after.url_contains and self._after.url_contains in (
            self._page.url or ""
        ):
            return True
        auth_ok = self._page.locator("#hiddenFieldAuthentificationOK")
        try:
            if auth_ok.count() and auth_ok.first.get_attribute("value") == "True":
                return True
        except Exception:
            pass
        return not self._still_on_login_form()

    def _detect_failure_message(self) -> bool:
        return bool(self._failure_message())

    def _failure_message(self) -> str:
        try:
            body = (self._page.inner_text("body") or "").lower()
        except Exception:
            return ""
        for text in self._login.failure_texts:
            needle = text.lower().strip()
            if needle and needle in body:
                return f"Login failed: page contains '{text}'"
        return ""
