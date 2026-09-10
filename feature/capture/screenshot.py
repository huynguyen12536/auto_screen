"""Screenshot helpers using mss + Pillow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from typing import Any

import mss
from PIL import Image

from utils.logger import get_logger
from utils.paths import SCREENSHOT_DIR, ensure_runtime_dirs, resolve_project_path

logger = get_logger("capture")


class ScreenshotCapture:
    def __init__(
        self, output_dir: str | Path | None = None, image_format: str = "png"
    ) -> None:
        ensure_runtime_dirs()
        if output_dir is None:
            self._output_dir = SCREENSHOT_DIR
        else:
            self._output_dir = resolve_project_path(str(output_dir))
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._image_format = image_format.lower().lstrip(".")

    def capture_screen(self, output_path: Path | None = None) -> Path:
        with mss.mss() as sct:
            return self._save(sct.grab(sct.monitors[0]), output_path)

    def capture_monitor(
        self, monitor: int = 1, output_path: Path | None = None
    ) -> Path:
        with mss.mss() as sct:
            if monitor < 1 or monitor >= len(sct.monitors):
                raise ValueError(f"Monitor {monitor} is not available")
            return self._save(sct.grab(sct.monitors[monitor]), output_path)

    def capture_window(
        self,
        bounds: tuple[int, int, int, int],
        output_path: Path | None = None,
    ) -> Path:
        left, top, width, height = bounds
        return self.capture_region(left, top, width, height, output_path)

    def capture_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        output_path: Path | None = None,
    ) -> Path:
        if width <= 1 or height <= 1:
            raise ValueError("Capture region is too small")
        region = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height),
        }
        with mss.mss() as sct:
            return self._save(sct.grab(region), output_path)

    def build_output_path(self, stem: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{stem}_{stamp}.{self._image_format}"
        return self._output_dir / filename

    def _save(self, shot: Any, output_path: Path | None) -> Path:
        path = output_path or self.build_output_path("screenshot")
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        image.save(path)
        logger.info("Screenshot saved | path=%s", path)
        return path


def capture_screen() -> Path:
    return ScreenshotCapture().capture_screen()
