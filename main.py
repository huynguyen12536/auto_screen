"""Browser Automation Tool entrypoint.

Opens TARGET_URL, captures before-login screenshot, logs in once,
waits for Agendas palette button, screenshots, opens Agendas, then
screenshots again after load.
"""

from __future__ import annotations

import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.browser import title_hint_from_url
from config.settings import clear_settings_cache, load_settings
from feature.agendas import AgendasNavigationError
from feature.login import LoginFailedError
from feature.opencv.runtime import configure_opencv
from services.browser_automation_service import BrowserAutomationService
from utils.logger import get_logger, setup_logging
from utils.paths import ensure_runtime_dirs


def main() -> None:
    clear_settings_cache()
    settings = load_settings()
    ensure_runtime_dirs()
    setup_logging(level=settings.logging.level)
    logger = get_logger("browser")
    opencv = configure_opencv(settings.opencv)
    hint = title_hint_from_url(settings.target_url) or "page"

    print("Browser Automation Tool")
    print(f"Environment: {settings.environment}")
    print("Configuration loaded successfully")
    print("Runtime directories ready")
    print(f"OpenCV configured: {opencv.version}")
    print(
        f"Browser engine: {settings.browser.engine} "
        f"(headless={settings.browser.headless})"
    )
    if not settings.browser.headless:
        print("Browser window will open; minimize is OK for capture.")
    print(f"Ready selector: {settings.browser.ready_selector}")
    print(f"Opening: {settings.target_url}")
    print(f"Login user: {settings.masked_username()}")

    logger.info("Browser automation started")
    logger.info("OpenCV configured | version=%s", opencv.version)

    service = BrowserAutomationService(settings)
    try:
        service.open_target()
        before_login = service.capture_current_page(f"{hint}_before_login")
        print(f"Before-login screenshot: {before_login}")
        logger.info("Before-login screenshot captured | path=%s", before_login)

        service.login()

        (
            before_agendas,
            after_agendas,
            after_planning,
            after_ressource,
            after_vue,
            vacations_db,
        ) = service.open_agendas(stem_prefix=hint)
        print(f"Vacations SQLite: {vacations_db}")
        logger.info(
            "Agendas screenshots | before=%s after=%s planning=%s ressource=%s vue=%s db=%s",
            before_agendas,
            after_agendas,
            after_planning,
            after_ressource,
            after_vue,
            vacations_db,
        )
    except (LoginFailedError, AgendasNavigationError) as exc:
        print(f"Flow failed: {exc}")
        logger.error("Flow failed (no retry) | reason=%s", exc)
        sys.exit(1)
    except PlaywrightTimeoutError:
        print("Website load timeout")
        logger.error("Website load timeout")
        raise
    finally:
        service.close()


if __name__ == "__main__":
    main()
