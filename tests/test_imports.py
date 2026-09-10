"""Import smoke tests.

OCR and vision modules must import without loading EasyOCR models.
"""

import importlib
import sys

import vision.ocr as ocr_module


def test_ocr_module_does_not_preload_easyocr():
    assert "easyocr" not in sys.modules
    assert ocr_module._EASYOCR_READER is None


def test_core_packages_import():
    browser = importlib.import_module("automation.browser")
    importlib.import_module("automation.keyboard")
    importlib.import_module("automation.mouse")
    importlib.import_module("automation.window")
    screenshot = importlib.import_module("feature.capture.screenshot")
    opencv_runtime = importlib.import_module("feature.opencv.runtime")
    importlib.import_module("config.settings")
    importlib.import_module("services.browser_automation_service")
    matcher = importlib.import_module("vision.image_matcher")
    ocr = importlib.import_module("vision.ocr")

    assert browser.BrowserController
    assert screenshot.ScreenshotCapture
    assert opencv_runtime.configure_opencv
    assert ocr.OcrEngine
    assert matcher.ImageMatcher
    assert "easyocr" not in sys.modules
