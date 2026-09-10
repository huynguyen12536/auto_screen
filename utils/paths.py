from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
FEATURE_CONFIG_DIR = CONFIG_DIR / "feature"
CAPTURE_CONFIG_FILE = FEATURE_CONFIG_DIR / "capture.yaml"
OPENCV_CONFIG_FILE = FEATURE_CONFIG_DIR / "opencv.yaml"
LOGIN_CONFIG_FILE = FEATURE_CONFIG_DIR / "login.yaml"

RUNTIME_DIR = PROJECT_ROOT / "runtime"
SCREENSHOT_DIR = RUNTIME_DIR / "screenshots"
LOG_DIR = RUNTIME_DIR / "logs"
TEMP_DIR = RUNTIME_DIR / "temp"

APP_LOG_FILE = LOG_DIR / "app.log"


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def ensure_runtime_dirs() -> None:
    """Create runtime folders if they do not already exist."""
    for directory in (RUNTIME_DIR, SCREENSHOT_DIR, LOG_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)
