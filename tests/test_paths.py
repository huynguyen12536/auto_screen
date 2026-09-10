from utils.paths import (
    FEATURE_CONFIG_DIR,
    LOG_DIR,
    OPENCV_CONFIG_FILE,
    PROJECT_ROOT,
    RUNTIME_DIR,
    SCREENSHOT_DIR,
    TEMP_DIR,
    ensure_runtime_dirs,
)


def test_runtime_paths_resolve_under_project_root():
    assert RUNTIME_DIR == PROJECT_ROOT / "runtime"
    assert SCREENSHOT_DIR == RUNTIME_DIR / "screenshots"
    assert LOG_DIR == RUNTIME_DIR / "logs"
    assert TEMP_DIR == RUNTIME_DIR / "temp"
    assert FEATURE_CONFIG_DIR == PROJECT_ROOT / "config" / "feature"
    assert OPENCV_CONFIG_FILE == FEATURE_CONFIG_DIR / "opencv.yaml"
    assert PROJECT_ROOT.name


def test_ensure_runtime_dirs_creates_folders():
    ensure_runtime_dirs()
    assert RUNTIME_DIR.is_dir()
    assert SCREENSHOT_DIR.is_dir()
    assert LOG_DIR.is_dir()
    assert TEMP_DIR.is_dir()
