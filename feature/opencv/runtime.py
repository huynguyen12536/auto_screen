"""OpenCV (cv2) runtime configuration.

This prepares OpenCV for later image matching. It does not run
template matching or capture screenshots.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2

from config.settings import OpenCvSettings

_INTERPOLATION = {
    "nearest": cv2.INTER_NEAREST,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "area": cv2.INTER_AREA,
    "lanczos4": cv2.INTER_LANCZOS4,
}

_MATCH_METHODS = {
    "tm_ccoeff": cv2.TM_CCOEFF,
    "tm_ccoeff_normed": cv2.TM_CCOEFF_NORMED,
    "tm_ccorr": cv2.TM_CCORR,
    "tm_ccorr_normed": cv2.TM_CCORR_NORMED,
    "tm_sqdiff": cv2.TM_SQDIFF,
    "tm_sqdiff_normed": cv2.TM_SQDIFF_NORMED,
}


@dataclass(frozen=True)
class OpenCvRuntime:
    version: str
    interpolation: int
    match_method: int


def configure_opencv(settings: OpenCvSettings) -> OpenCvRuntime:
    """Apply project OpenCV settings and return resolved cv2 flags."""
    if not settings.enabled:
        return OpenCvRuntime(
            version=cv2.__version__,
            interpolation=_interpolation_flag(settings.interpolation),
            match_method=_match_method_flag(settings.match_method),
        )

    cv2.setUseOptimized(settings.use_optimized)
    if settings.num_threads > 0:
        cv2.setNumThreads(settings.num_threads)

    return OpenCvRuntime(
        version=cv2.__version__,
        interpolation=_interpolation_flag(settings.interpolation),
        match_method=_match_method_flag(settings.match_method),
    )


def _interpolation_flag(name: str) -> int:
    try:
        return _INTERPOLATION[name]
    except KeyError as exc:
        allowed = ", ".join(sorted(_INTERPOLATION))
        raise ValueError(
            f"Unknown OpenCV interpolation: {name}. Use: {allowed}"
        ) from exc


def _match_method_flag(name: str) -> int:
    try:
        return _MATCH_METHODS[name]
    except KeyError as exc:
        allowed = ", ".join(sorted(_MATCH_METHODS))
        raise ValueError(
            f"Unknown OpenCV match method: {name}. Use: {allowed}"
        ) from exc
