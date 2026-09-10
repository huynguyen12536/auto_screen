"""Browser Automation Tool entrypoint.

Opens TARGET_URL with Playwright and captures a before-login screenshot.
Waits for .mainContainer to be visible to avoid black captures.
"""

from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.browser import title_hint_from_url
from config.settings import clear_settings_cache, load_settings
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
    print(f"Ready selector: {settings.browser.ready_selector}")
    print(f"Opening: {settings.target_url}")

    logger.info("Browser automation started")
    logger.info("OpenCV configured | version=%s", opencv.version)

    service = BrowserAutomationService(settings)
    try:
        service.open_target()
        screenshot_path = service.capture_current_page(f"{hint}_before_login")
        print(f"Screenshot saved: {screenshot_path}")
        logger.info("Before-login screenshot captured | path=%s", screenshot_path)
    except PlaywrightTimeoutError:
        print("Website load timeout")
        logger.error("Website load timeout")
        raise
    finally:
        service.close()


if __name__ == "__main__":
    main()
