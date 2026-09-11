"""Project settings loader.

All modules should receive settings from here instead of reading
.env or config.yaml directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from jsonschema import validate

from utils.paths import (
    CAPTURE_CONFIG_FILE,
    CONFIG_FILE,
    LOGIN_CONFIG_FILE,
    OPENCV_CONFIG_FILE,
    PROJECT_ROOT,
)

CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["browser", "timing", "logging"],
    "properties": {
        "browser": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "engine": {"type": "string", "enum": ["playwright", "desktop"]},
                "headless": {"type": "boolean"},
                "guest": {"type": "boolean"},
                "viewport": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer", "minimum": 1},
                        "height": {"type": "integer", "minimum": 1},
                    },
                },
                "ready_selector": {"type": "string", "minLength": 1},
                "ready_timeout_ms": {"type": "integer", "minimum": 1000},
            },
        },
        "timing": {
            "type": "object",
            "required": [
                "browser_start_timeout",
                "page_load_delay",
                "action_delay",
            ],
            "properties": {
                "browser_start_timeout": {"type": "number"},
                "page_load_delay": {"type": "number"},
                "action_delay": {"type": "number"},
                "human": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "min_time": {"type": "number"},
                        "max_time": {"type": "number"},
                        "mean": {"type": "number"},
                        "std_dev": {"type": "number"},
                    },
                },
            },
        },
        "logging": {
            "type": "object",
            "required": ["level"],
            "properties": {"level": {"type": "string", "minLength": 1}},
        },
    },
}

CAPTURE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["directory", "format"],
    "properties": {
        "directory": {"type": "string", "minLength": 1},
        "format": {"type": "string", "minLength": 1},
        "full_page": {"type": "boolean"},
    },
}

OPENCV_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["enabled", "use_optimized", "num_threads", "color", "match"],
    "properties": {
        "enabled": {"type": "boolean"},
        "use_optimized": {"type": "boolean"},
        "num_threads": {"type": "integer"},
        "color": {
            "type": "object",
            "required": ["use_grayscale", "interpolation"],
            "properties": {
                "use_grayscale": {"type": "boolean"},
                "interpolation": {"type": "string", "minLength": 1},
            },
        },
        "match": {
            "type": "object",
            "required": ["method", "threshold"],
            "properties": {
                "method": {"type": "string", "minLength": 1},
                "threshold": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
    },
}

LOGIN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["submit_wait", "selectors"],
    "properties": {
        "submit_wait": {"type": "number"},
        "type_interval": {"type": "number"},
        "selectors": {
            "type": "object",
            "required": ["username", "password", "submit"],
            "properties": {
                "username": {"type": "string", "minLength": 1},
                "password": {"type": "string", "minLength": 1},
                "submit": {"type": "string", "minLength": 1},
            },
        },
        "after_login": {
            "type": "object",
            "properties": {
                "ready_selector": {"type": "string", "minLength": 1},
                "url_contains": {"type": "string"},
                "loading_hidden_selector": {"type": "string"},
                "agendas": {
                    "type": "object",
                    "properties": {
                        "button": {"type": "string", "minLength": 1},
                        "after_ready_selector": {"type": "string", "minLength": 1},
                        "url_contains": {"type": "string"},
                        "planning": {
                            "type": "object",
                            "properties": {
                                "dropdown_button": {"type": "string", "minLength": 1},
                                "option": {"type": "string", "minLength": 1},
                                "option_label": {"type": "string", "minLength": 1},
                                "selected_value": {"type": "string"},
                                "ready_after_select": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                            },
                        },
                        "ressource": {
                            "type": "object",
                            "properties": {
                                "dropdown_button": {"type": "string", "minLength": 1},
                                "select_all": {"type": "string", "minLength": 1},
                                "change_debounce_seconds": {"type": "number"},
                                "ready_after_select": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                            },
                        },
                        "vue": {
                            "type": "object",
                            "properties": {
                                "dropdown_button": {"type": "string", "minLength": 1},
                                "option": {"type": "string", "minLength": 1},
                                "option_label": {"type": "string", "minLength": 1},
                                "selected_value": {"type": "string"},
                                "ready_after_select": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                            },
                        },
                    },
                },
            },
        },
        "failure_texts": {
            "type": "array",
            "items": {"type": "string"},
        },
        "email": {"type": "object"},
        "password": {"type": "object"},
        "submit": {"type": "object"},
    },
}


@dataclass(frozen=True)
class ViewportSettings:
    width: int
    height: int


@dataclass(frozen=True)
class BrowserSettings:
    name: str
    engine: str
    headless: bool
    guest: bool
    viewport: ViewportSettings
    ready_selector: str
    ready_timeout_ms: int


@dataclass(frozen=True)
class HumanDelaySettings:
    enabled: bool
    min_time: float
    max_time: float
    mean: float
    std_dev: float


@dataclass(frozen=True)
class TimingSettings:
    browser_start_timeout: float
    page_load_delay: float
    action_delay: float
    human: HumanDelaySettings


@dataclass(frozen=True)
class CaptureSettings:
    directory: str
    format: str
    full_page: bool


@dataclass(frozen=True)
class LoggingSettings:
    level: str


@dataclass(frozen=True)
class OpenCvSettings:
    enabled: bool
    use_optimized: bool
    num_threads: int
    use_grayscale: bool
    interpolation: str
    match_method: str
    match_threshold: float


@dataclass(frozen=True)
class LoginSelectors:
    username: str
    password: str
    submit: str


@dataclass(frozen=True)
class PlanningSelectSettings:
    dropdown_button: str
    option: str
    option_label: str
    selected_value: str
    ready_after_select: str


@dataclass(frozen=True)
class RessourceSelectSettings:
    dropdown_button: str
    select_all: str
    ready_after_select: str
    change_debounce_seconds: float = 1.2


@dataclass(frozen=True)
class AgendasSettings:
    button: str
    after_ready_selector: str
    url_contains: str = "4008001"
    planning: PlanningSelectSettings | None = None
    ressource: RessourceSelectSettings | None = None
    vue: PlanningSelectSettings | None = None


@dataclass(frozen=True)
class AfterLoginSettings:
    ready_selector: str
    url_contains: str = ""
    loading_hidden_selector: str = "#loadingScreen"
    agendas: AgendasSettings | None = None


@dataclass(frozen=True)
class LoginSettings:
    submit_wait: float
    selectors: LoginSelectors
    failure_texts: tuple[str, ...]
    after_login: AfterLoginSettings
    type_interval: float = 0.04


@dataclass(frozen=True)
class BackendImportSettings:
    enabled: bool
    base_url: str
    bot_email: str
    bot_password: str
    timeout_seconds: float


@dataclass(frozen=True)
class Settings:
    environment: str
    browser: BrowserSettings
    timing: TimingSettings
    capture: CaptureSettings
    logging: LoggingSettings
    opencv: OpenCvSettings
    login: LoginSettings
    target_url: str
    target_username: str
    target_password: str
    backend_import: BackendImportSettings

    def masked_username(self) -> str:
        value = self.target_username
        if not value:
            return ""
        if len(value) <= 4:
            return "********"
        return f"{value[:2]}********{value[-2:]}"

    def masked_password(self) -> str:
        return "********" if self.target_password else ""


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_yaml_config(path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root")
    validate(instance=data, schema=schema)
    return data


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if not value:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if not value:
        return default
    return float(value)


def _build_login_settings(raw: dict[str, Any]) -> LoginSettings:
    selectors = raw["selectors"]
    failure_texts = tuple(str(item) for item in (raw.get("failure_texts") or []))
    after_raw = raw.get("after_login") or {}
    agendas_raw = after_raw.get("agendas") or {}
    agendas = None
    if agendas_raw:
        planning_raw = agendas_raw.get("planning") or {}
        planning = None
        if planning_raw:
            planning = PlanningSelectSettings(
                dropdown_button=str(
                    planning_raw.get(
                        "dropdown_button",
                        'button.drop-down[control-id="DDLChoixPlanningData"]',
                    )
                ),
                option=str(
                    planning_raw.get("option", "#DDLChoixPlanningData_ctl01")
                ),
                option_label=str(planning_raw.get("option_label", "BRESSUIRE")),
                selected_value=str(planning_raw.get("selected_value", "0")),
                ready_after_select=str(
                    planning_raw.get(
                        "ready_after_select",
                        "#glyphBtnFonctionnaliteEnCours.prev-calendar",
                    )
                ),
            )
        ressource_raw = agendas_raw.get("ressource") or {}
        ressource = None
        if ressource_raw:
            ressource = RessourceSelectSettings(
                dropdown_button=str(
                    ressource_raw.get(
                        "dropdown_button",
                        'button.drop-down[control-id="DDLChoixRessourceMultipleData"]',
                    )
                ),
                select_all=str(
                    ressource_raw.get(
                        "select_all",
                        "#DDLChoixRessourceMultipleData_chkAll",
                    )
                ),
                ready_after_select=str(
                    ressource_raw.get(
                        "ready_after_select",
                        "#glyphBtnFonctionnaliteEnCours.prev-calendar",
                    )
                ),
                change_debounce_seconds=float(
                    ressource_raw.get("change_debounce_seconds", 1.2)
                ),
            )
        vue_raw = agendas_raw.get("vue") or {}
        vue = None
        if vue_raw:
            vue = PlanningSelectSettings(
                dropdown_button=str(
                    vue_raw.get(
                        "dropdown_button",
                        'button.drop-down[control-id="ucChoixDesVues_DDLChoixVue"]',
                    )
                ),
                option=str(
                    vue_raw.get("option", "#ucChoixDesVues_DDLChoixVue_ctl00")
                ),
                option_label=str(vue_raw.get("option_label", "File d'attente")),
                selected_value=str(vue_raw.get("selected_value", "6")),
                ready_after_select=str(
                    vue_raw.get(
                        "ready_after_select",
                        "#glyphBtnFonctionnaliteEnCours.prev-calendar",
                    )
                ),
            )
        agendas = AgendasSettings(
            button=str(
                agendas_raw.get("button", "#repeaterPalette_ctl01_btnDiv")
            ),
            after_ready_selector=str(
                agendas_raw.get(
                    "after_ready_selector",
                    "#repeaterPalette_ctl01_btnDiv.SelectedItem",
                )
            ),
            url_contains=str(agendas_raw.get("url_contains", "4008001")),
            planning=planning,
            ressource=ressource,
            vue=vue,
        )
    return LoginSettings(
        submit_wait=float(raw["submit_wait"]),
        selectors=LoginSelectors(
            username=str(selectors["username"]),
            password=str(selectors["password"]),
            submit=str(selectors["submit"]),
        ),
        failure_texts=failure_texts,
        after_login=AfterLoginSettings(
            ready_selector=str(
                after_raw.get("ready_selector", "#repeaterPalette_ctl01_btnDiv")
            ),
            url_contains=str(after_raw.get("url_contains", "accueilv2.aspx")),
            loading_hidden_selector=str(
                after_raw.get("loading_hidden_selector", "#loadingScreen")
            ),
            agendas=agendas,
        ),
        type_interval=float(raw.get("type_interval", 0.04)),
    )


def _build_human_delay(raw: dict[str, Any]) -> HumanDelaySettings:
    return HumanDelaySettings(
        enabled=bool(raw.get("enabled", True)),
        min_time=float(raw.get("min_time", 0.25)),
        max_time=float(raw.get("max_time", 1.2)),
        mean=float(raw.get("mean", 0.45)),
        std_dev=float(raw.get("std_dev", 0.15)),
    )


def _build_settings(
    raw: dict[str, Any],
    capture_raw: dict[str, Any],
    opencv_raw: dict[str, Any],
    login_raw: dict[str, Any],
) -> Settings:
    browser_name = _env("BROWSER", str(raw["browser"]["name"]))
    screenshot_dir = _env("SCREENSHOT_DIR", str(capture_raw["directory"]))
    log_level = _env("LOG_LEVEL", str(raw["logging"]["level"]))
    environment = _env("ENVIRONMENT", "development")
    opencv_threads = _env_int("OPENCV_NUM_THREADS", int(opencv_raw["num_threads"]))
    opencv_threshold = _env_float(
        "OPENCV_MATCH_THRESHOLD", float(opencv_raw["match"]["threshold"])
    )

    return Settings(
        environment=environment or "development",
        browser=BrowserSettings(
            name=browser_name or "chrome",
            engine=str(raw["browser"].get("engine", "playwright")).lower(),
            headless=bool(raw["browser"].get("headless", False)),
            guest=bool(raw["browser"].get("guest", True)),
            viewport=ViewportSettings(
                width=int((raw["browser"].get("viewport") or {}).get("width", 1920)),
                height=int((raw["browser"].get("viewport") or {}).get("height", 1080)),
            ),
            ready_selector=str(raw["browser"].get("ready_selector", ".mainContainer")),
            ready_timeout_ms=int(raw["browser"].get("ready_timeout_ms", 120_000)),
        ),
        timing=TimingSettings(
            browser_start_timeout=float(raw["timing"]["browser_start_timeout"]),
            page_load_delay=float(raw["timing"]["page_load_delay"]),
            action_delay=float(raw["timing"]["action_delay"]),
            human=_build_human_delay(raw["timing"].get("human") or {}),
        ),
        capture=CaptureSettings(
            directory=screenshot_dir,
            format=str(capture_raw["format"]),
            full_page=bool(capture_raw.get("full_page", True)),
        ),
        logging=LoggingSettings(level=log_level or "INFO"),
        opencv=OpenCvSettings(
            enabled=bool(opencv_raw["enabled"]),
            use_optimized=bool(opencv_raw["use_optimized"]),
            num_threads=opencv_threads,
            use_grayscale=bool(opencv_raw["color"]["use_grayscale"]),
            interpolation=str(opencv_raw["color"]["interpolation"]),
            match_method=str(opencv_raw["match"]["method"]),
            match_threshold=opencv_threshold,
        ),
        login=_build_login_settings(login_raw),
        target_url=_env("TARGET_URL"),
        target_username=_env("TARGET_USERNAME"),
        target_password=_env("TARGET_PASSWORD"),
        backend_import=BackendImportSettings(
            enabled=_env_bool("BACKEND_IMPORT_ENABLED", True),
            base_url=_env(
                "BACKEND_API_URL",
                "https://sist79-be.vm.dfm-europe.com",
            ),
            bot_email=_env("UEGAR_BOT_EMAIL", "uegar.bot@internal.local"),
            bot_password=_env("UEGAR_BOT_PASSWORD"),
            timeout_seconds=_env_float("BACKEND_IMPORT_TIMEOUT_SECONDS", 120.0),
        ),
    )


def clear_settings_cache() -> None:
    load_settings.cache_clear()


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load .env, core config, feature configs, then apply env overrides."""
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    raw = _load_yaml_config(CONFIG_FILE, CONFIG_SCHEMA)
    capture_raw = _load_yaml_config(CAPTURE_CONFIG_FILE, CAPTURE_SCHEMA)
    opencv_raw = _load_yaml_config(OPENCV_CONFIG_FILE, OPENCV_SCHEMA)
    login_raw = _load_yaml_config(LOGIN_CONFIG_FILE, LOGIN_SCHEMA)
    return _build_settings(raw, capture_raw, opencv_raw, login_raw)
