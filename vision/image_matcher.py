"""Image matching skeleton.

Later this may use opencv-python, numpy, scikit-image, and imagehash.
No matching logic runs in the setup phase.
"""

from __future__ import annotations

from pathlib import Path


class ImageMatcher:
    def find_template(self, screenshot: Path, template: Path) -> tuple[int, int] | None:
        raise NotImplementedError(
            "Image matching is not implemented in the setup phase."
        )
