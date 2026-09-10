"""Desktop browser controller for Windows Chrome."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from utils.logger import get_logger

logger = get_logger("browser")


def title_hint_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    parts = [part for part in host.split(".") if part]
    if len(parts) >= 2:
        return parts[-2]
    return host or url


class BrowserController:
    def __init__(self, browser_name: str = "chrome", guest: bool = True) -> None:
        self._browser_name = browser_name.lower()
        self._guest = guest
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        self._launch()

    def navigate(self, url: str) -> None:
        if not url:
            raise ValueError("TARGET_URL is empty")
        self._launch(url)

    def close(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        self._process = None

    def _launch(self, url: str | None = None) -> None:
        executable = self._resolve_executable()
        command = [str(executable)]
        if self._guest:
            command.append("--guest")
        command.extend(
            [
                "--new-window",
                "--start-maximized",
                "--no-first-run",
                "--disable-session-crashed-bubble",
            ]
        )
        if url:
            command.append(url)
        logger.info("Starting browser | name=%s", self._browser_name)
        self._process = subprocess.Popen(command)

    def _resolve_executable(self) -> Path:
        if self._browser_name != "chrome":
            raise ValueError(f"Unsupported browser: {self._browser_name}")
        candidates = []
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        program_files_x86 = os.environ.get(
            "PROGRAMFILES(X86)", r"C:\Program Files (x86)"
        )
        candidates.extend(
            [
                Path(program_files)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
                Path(program_files_x86)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
                Path(local_app_data)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
            ]
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError("Google Chrome was not found on this Windows machine.")
