from utils.timing import (
    exponential_delay,
    human_delay,
    sleep_human,
    uniform_delay,
)


def test_human_delay_is_clamped():
    for _ in range(30):
        value = human_delay(min_time=0.4, max_time=0.8, mean=0.6, std_dev=0.5)
        assert 0.4 <= value <= 0.8


def test_uniform_delay_is_within_range():
    for _ in range(20):
        value = uniform_delay(0.2, 0.5)
        assert 0.2 <= value <= 0.5


def test_exponential_delay_is_within_range():
    for _ in range(20):
        value = exponential_delay(mean=0.5, min_time=0.1, max_time=1.0)
        assert 0.1 <= value <= 1.0


def test_sleep_human_returns_waited_seconds(monkeypatch):
    waited: list[float] = []

    def fake_sleep(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr("utils.timing.sleep", fake_sleep)
    delay = sleep_human(min_time=0.3, max_time=0.3, mean=0.3, std_dev=0.0)
    assert delay == 0.3
    assert waited == [0.3]
