"""One-off: login then dump page state until mainContainer or timeout."""
from __future__ import annotations

import time
from pathlib import Path

from config.settings import clear_settings_cache, load_settings
from automation.playwright_browser import PlaywrightBrowserController
from utils.logger import setup_logging
from utils.paths import ensure_runtime_dirs

OUT = Path("runtime/debug_after_login")


def snapshot(page, label: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%H%M%S")
    path = OUT / f"{stamp}_{label}"
    try:
        url = page.url
        title = page.title()
        has_main = page.locator(".mainContainer").count()
        main_vis = False
        main_len = 0
        try:
            loc = page.locator(".mainContainer").first
            main_vis = loc.is_visible()
            if main_vis:
                main_len = len((loc.inner_text() or "").strip())
        except Exception:
            pass
        user_vis = False
        try:
            user_vis = page.locator(
                "#ucAuthenticationForm1_textBoxIdentifiant"
            ).is_visible()
        except Exception:
            pass
        auth = ""
        try:
            auth = page.locator("#hiddenFieldAuthentificationOK").get_attribute(
                "value"
            )
        except Exception:
            pass
        loading = False
        try:
            loading = page.locator("#loadingScreen").is_visible()
        except Exception:
            pass
        body_len = 0
        try:
            body_len = len((page.inner_text("body") or "").strip())
        except Exception:
            pass
        line = (
            f"{label} url={url!r} title={title!r} auth={auth!r} "
            f"main_count={has_main} main_vis={main_vis} main_len={main_len} "
            f"user_vis={user_vis} loading={loading} body_len={body_len}"
        )
        print(line, flush=True)
        (path.with_suffix(".txt")).write_text(line + "\n", encoding="utf-8")
        page.screenshot(path=str(path.with_suffix(".png")), full_page=True)
        html = page.content()
        (path.with_suffix(".html")).write_text(html[:200_000], encoding="utf-8")
    except Exception as exc:
        print(f"{label} snapshot failed: {exc}", flush=True)


def main() -> None:
    clear_settings_cache()
    settings = load_settings()
    ensure_runtime_dirs()
    setup_logging(level=settings.logging.level)
    pw = PlaywrightBrowserController(
        headless=settings.browser.headless,
        viewport_width=settings.browser.viewport.width,
        viewport_height=settings.browser.viewport.height,
        navigation_timeout_ms=settings.timing.browser_start_timeout * 1000,
        ready_selector=settings.browser.ready_selector,
        ready_timeout_ms=settings.browser.ready_timeout_ms,
    )
    try:
        pw.navigate(settings.target_url, wait_until="commit")
        snapshot(pw.page, "before_login")
        user = settings.target_username
        password = settings.target_password
        pw.page.fill("#ucAuthenticationForm1_textBoxIdentifiant", user)
        pw.page.fill("#ucAuthenticationForm1_textBoxPassword", password)
        snapshot(pw.page, "filled")
        pw.page.click("#ucAuthenticationForm1_lnkConfirmer")
        deadline = time.time() + 180
        n = 0
        while time.time() < deadline:
            n += 1
            snapshot(pw.page, f"poll_{n:02d}")
            try:
                user_vis = pw.page.locator(
                    "#ucAuthenticationForm1_textBoxIdentifiant"
                ).is_visible()
                main_vis = pw.page.locator(".mainContainer").first.is_visible()
                main_len = (
                    len(
                        (
                            pw.page.locator(".mainContainer").first.inner_text() or ""
                        ).strip()
                    )
                    if main_vis
                    else 0
                )
                if (not user_vis) and main_vis and main_len > 40:
                    print("READY condition met", flush=True)
                    break
            except Exception:
                pass
            time.sleep(5)
    finally:
        pw.close()


if __name__ == "__main__":
    main()
