"""OCR skeleton.

EasyOCR / Tesseract models must not load on import or startup.
This module stays lazy until a later phase implements OCR.
"""

from __future__ import annotations

from pathlib import Path

# Intentionally unused until a later phase. Keep None so imports stay cheap.
_EASYOCR_READER = None


class OcrEngine:
    def __init__(self) -> None:
        self._easyocr_reader = None

    def read_text(self, image_path: Path | str) -> str:
        raise NotImplementedError("OCR is not implemented in the setup phase.")
