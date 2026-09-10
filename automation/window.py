"""Window helpers using pygetwindow / pywin32."""

from __future__ import annotations

import ctypes
from typing import Any

import pygetwindow as gw

from utils.logger import get_logger
from utils.timing import sleep, wait_until

logger = get_logger("window")
_DPI_ENABLED = False
_OFFSCREEN_MINIMIZED = -10000


def enable_dpi_awareness() -> None:
    global _DPI_ENABLED
    if _DPI_ENABLED:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
    _DPI_ENABLED = True


def looks_minimized(left: int, top: int, width: int, height: int) -> bool:
    """Windows parks minimized windows off-screen, often around -32000."""
    return (
        left <= _OFFSCREEN_MINIMIZED
        or top <= _OFFSCREEN_MINIMIZED
        or width <= 1
        or height <= 1
    )


class WindowController:
    def __init__(self) -> None:
        enable_dpi_awareness()

    def list_hwnds(self) -> set[int]:
        hwnds: set[int] = set()
        for window in gw.getAllWindows():
            hwnd = getattr(window, "_hWnd", None)
            if hwnd:
                hwnds.add(int(hwnd))
        return hwnds

    def find_browser_window(
        self, title_hint: str = "", exclude_hwnds: set[int] | None = None
    ) -> Any:
        hint = title_hint.lower().strip()
        excluded = exclude_hwnds or set()
        for window in gw.getAllWindows():
            title = (window.title or "").strip()
            if not title:
                continue
            hwnd = getattr(window, "_hWnd", None)
            if hwnd is not None and int(hwnd) in excluded:
                continue
            if hint and hint not in title.lower():
                continue
            return window
        return None

    def is_minimized(self, window: Any = None) -> bool:
        window = self._require(window)
        if getattr(window, "isMinimized", False):
            return True
        hwnd = getattr(window, "_hWnd", None)
        if hwnd:
            import win32gui

            if win32gui.IsIconic(int(hwnd)):
                return True
        left, top, width, height = self.get_bounds(window)
        return looks_minimized(left, top, width, height)

    def has_visible_bounds(self, window: Any = None) -> bool:
        window = self._require(window)
        if self.is_minimized(window):
            return False
        _left, _top, width, height = self.get_bounds(window)
        return width > 50 and height > 50

    def prepare_for_capture(self, window: Any = None, timeout: float = 5.0) -> Any:
        """Restore/focus a minimized window so screen capture can see it."""
        window = self._refresh(self._require(window))
        if self.is_minimized(window):
            logger.info(
                "Window is minimized, restoring before capture | title=%s",
                window.title,
            )
            self.restore(window)
            window = self._refresh(window)
        self.focus(window)
        window = self._refresh(window)
        self.maximize(window)
        window = self._refresh(window)
        wait_until(
            lambda: self.has_visible_bounds(self._refresh(window)),
            timeout=timeout,
            message="Browser window is still minimized or not visible",
        )
        sleep(0.3)
        return self._refresh(window)

    def focus(self, window: Any = None) -> None:
        window = self._require(window)
        if self.is_minimized(window):
            self.restore(window)
            window = self._refresh(window)
        self._foreground(window)
        logger.info("Focused window | title=%s", window.title)

    def restore(self, window: Any = None) -> None:
        window = self._require(window)
        hwnd = getattr(window, "_hWnd", None)
        if hwnd:
            import win32con
            import win32gui

            win32gui.ShowWindow(int(hwnd), win32con.SW_RESTORE)
        else:
            window.restore()
        logger.info("Restored window | title=%s", window.title)

    def maximize(self, window: Any = None) -> None:
        window = self._require(window)
        if self.is_minimized(window):
            self.restore(window)
            window = self._refresh(window)
        window.maximize()
        sleep(0.2)
        logger.info("Maximized window | title=%s", window.title)

    def get_bounds(self, window: Any = None) -> tuple[int, int, int, int]:
        window = self._require(window)
        return (window.left, window.top, window.width, window.height)

    def _refresh(self, window: Any) -> Any:
        hwnd = getattr(window, "_hWnd", None)
        if hwnd is None:
            return window
        for candidate in gw.getAllWindows():
            if getattr(candidate, "_hWnd", None) == hwnd:
                return candidate
        return window

    def _require(self, window: Any) -> Any:
        if window is None:
            raise ValueError("Browser window is not available")
        return window

    def _foreground(self, window: Any) -> None:
        try:
            window.activate()
            return
        except Exception:
            logger.debug("pygetwindow activate failed, trying win32")
        hwnd = getattr(window, "_hWnd", None)
        if not hwnd:
            return
        import win32con
        import win32gui

        win32gui.ShowWindow(int(hwnd), win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(int(hwnd))
        except Exception:
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("%")
            win32gui.SetForegroundWindow(int(hwnd))
