from automation.browser import title_hint_from_url
from automation.window import looks_minimized


def test_title_hint_from_facebook_url():
    assert title_hint_from_url("https://www.facebook.com/") == "facebook"
    assert title_hint_from_url("https://facebook.com/login") == "facebook"


def test_minimized_bounds_are_detected():
    assert looks_minimized(-32000, -32000, 160, 28) is True
    assert looks_minimized(0, 0, 1, 1) is True
    assert looks_minimized(0, 0, 1920, 1080) is False
