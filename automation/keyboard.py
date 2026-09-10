"""Keyboard helpers wrapping pyautogui."""

from __future__ import annotations

import pyautogui

from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("keyboard")
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class KeyboardController:
    def hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys)
        logger.info("Hotkey | keys=%s", "+".join(keys))

    def type_text(self, text: str, interval: float = 0.0, secret: bool = False) -> None:
        pyautogui.write(text, interval=max(interval, 0.0))
        if secret:
            logger.info("Typed into password field")
        else:
            logger.info("Typed text | length=%s", len(text))

    def press(self, key: str) -> None:
        pyautogui.press(key)
        logger.info("Key press | key=%s", key)
        sleep(0.1)
