from config.settings import load_settings
from utils.paths import (
    CAPTURE_CONFIG_FILE,
    CONFIG_FILE,
    FEATURE_CONFIG_DIR,
    LOGIN_CONFIG_FILE,
    OPENCV_CONFIG_FILE,
)


def test_default_config_file_exists():
    assert CONFIG_FILE.is_file()
    assert CONFIG_FILE.name == "config.yaml"


def test_feature_capture_config_exists():
    assert FEATURE_CONFIG_DIR.is_dir()
    assert CAPTURE_CONFIG_FILE.is_file()
    assert CAPTURE_CONFIG_FILE.name == "capture.yaml"


def test_feature_opencv_config_exists():
    assert FEATURE_CONFIG_DIR.is_dir()
    assert OPENCV_CONFIG_FILE.is_file()
    assert OPENCV_CONFIG_FILE.name == "opencv.yaml"


def test_feature_login_config_exists():
    assert FEATURE_CONFIG_DIR.is_dir()
    assert LOGIN_CONFIG_FILE.is_file()
    assert LOGIN_CONFIG_FILE.name == "login.yaml"


def test_settings_load_successfully():
    settings = load_settings()
    assert settings.browser.name
    assert settings.browser.engine in {"playwright", "desktop"}
    assert settings.browser.viewport.width > 0
    assert settings.browser.ready_selector == ".mainContainer"
    assert settings.browser.ready_timeout_ms >= 1000
    assert settings.timing.browser_start_timeout > 0
    assert settings.timing.page_load_delay >= 0
    assert settings.timing.action_delay >= 0
    assert settings.timing.human.enabled is True
    assert settings.timing.human.min_time <= settings.timing.human.max_time
    assert settings.capture.directory
    assert settings.capture.format
    assert isinstance(settings.capture.full_page, bool)
    assert settings.logging.level
    assert settings.environment
    assert settings.opencv.enabled is True
    assert settings.target_url.startswith("http")
    assert settings.login.selectors.username
    assert settings.login.selectors.password
    assert settings.login.selectors.submit
    assert settings.login.after_login.ready_selector == "#repeaterPalette_ctl01_btnDiv"
    assert settings.login.after_login.agendas is not None
    assert settings.login.after_login.agendas.button == "#repeaterPalette_ctl01_btnDiv"
    assert settings.login.after_login.agendas.planning is not None
    assert settings.login.after_login.agendas.planning.option_label == "BRESSUIRE"
    assert settings.login.after_login.agendas.ressource is not None
    assert (
        settings.login.after_login.agendas.ressource.select_all
        == "#DDLChoixRessourceMultipleData_chkAll"
    )
    assert settings.login.after_login.agendas.vue is not None
    assert settings.login.after_login.agendas.vue.option_label == "File d'attente"
    assert settings.login.after_login.agendas.vue.selected_value == "6"
    assert settings.login.submit_wait > 0
    assert len(settings.login.failure_texts) > 0


def test_credentials_are_masked():
    settings = load_settings()
    if settings.target_password:
        assert settings.masked_password() == "********"
        assert settings.target_password not in settings.masked_password()
    else:
        assert settings.masked_password() == ""
    if settings.target_username and len(settings.target_username) > 4:
        assert settings.target_username not in settings.masked_username()
