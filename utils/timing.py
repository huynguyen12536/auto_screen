"""Timing helpers: fixed sleep, polling, and human-like delays."""

from __future__ import annotations

import random
import time
from collections.abc import Callable


def sleep(seconds: float) -> None:
    """Fixed sleep. Prefer sleep_human() for UI action gaps."""
    time.sleep(max(0.0, seconds))


def wait_until(
    condition: Callable[[], bool],
    timeout: float,
    interval: float = 0.2,
    message: str = "Condition not met within timeout",
) -> bool:
    """Poll until condition() is true or raise TimeoutError."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    raise TimeoutError(message)


def human_delay(
    min_time: float = 0.5,
    max_time: float = 2.0,
    mean: float = 1.0,
    std_dev: float = 0.3,
) -> float:
    """Gaussian delay (most values near mean), clamped to [min_time, max_time]."""
    if min_time > max_time:
        raise ValueError("min_time must be <= max_time")
    delay = random.gauss(mean, std_dev)
    return max(min_time, min(max_time, delay))


def uniform_delay(min_time: float = 0.5, max_time: float = 2.0) -> float:
    """Uniform random delay in [min_time, max_time]."""
    if min_time > max_time:
        raise ValueError("min_time must be <= max_time")
    return random.uniform(min_time, max_time)


def exponential_delay(
    mean: float = 1.0,
    min_time: float = 0.3,
    max_time: float = 3.0,
) -> float:
    """Exponential delay: usually short, occasionally longer."""
    if mean <= 0:
        raise ValueError("mean must be > 0")
    if min_time > max_time:
        raise ValueError("min_time must be <= max_time")
    delay = random.expovariate(1.0 / mean)
    return max(min_time, min(max_time, delay))


def sleep_human(
    min_time: float = 0.5,
    max_time: float = 2.0,
    mean: float = 1.0,
    std_dev: float = 0.3,
) -> float:
    """Sleep using human_delay and return the waited seconds."""
    delay = human_delay(min_time, max_time, mean, std_dev)
    sleep(delay)
    return delay
