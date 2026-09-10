from config.settings import load_settings
from feature.opencv.runtime import configure_opencv
from utils.paths import OPENCV_CONFIG_FILE


def test_opencv_config_file_exists():
    assert OPENCV_CONFIG_FILE.is_file()
    assert OPENCV_CONFIG_FILE.name == "opencv.yaml"


def test_opencv_settings_load():
    settings = load_settings()
    assert settings.opencv.enabled is True
    assert settings.opencv.match_method
    assert 0 <= settings.opencv.match_threshold <= 1
    assert settings.opencv.interpolation


def test_opencv_runtime_configures_cv2():
    import cv2

    runtime = configure_opencv(load_settings().opencv)
    assert runtime.version
    assert cv2.useOptimized() is True
    assert runtime.match_method == cv2.TM_CCOEFF_NORMED
    assert runtime.interpolation == cv2.INTER_LINEAR
