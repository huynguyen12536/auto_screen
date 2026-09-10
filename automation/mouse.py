"""Mouse helpers wrapping pyautogui."""

from __future__ import annotations

import pyautogui

from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("mouse")
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class MouseController:
    def click(self, x: int, y: int) -> None:
        pyautogui.click(x, y)
        logger.info("Mouse click | x=%s y=%s", x, y)
        sleep(0.15)

    def move(self, x: int, y: int) -> None:
        pyautogui.moveTo(x, y)
        logger.info("Mouse move | x=%s y=%s", x, y)

    def scroll(self, amount: int) -> None:
        pyautogui.scroll(amount)

    def click_ratio(
        self, bounds: tuple[int, int, int, int], x_ratio: float, y_ratio: float
    ) -> None:
        left, top, width, height = bounds
        x = left + int(width * x_ratio)
        y = top + int(height * y_ratio)
        self.click(x, y)
