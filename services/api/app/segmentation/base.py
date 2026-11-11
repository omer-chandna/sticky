"""Interchangeable foreground segmenters.

The default backend is classical OpenCV. A future model backend can implement
the same method without changing the pipeline. Generative inpainting is not
part of this interface.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Segmenter(Protocol):
    name: str

    def segment(
        self,
        image_rgb: np.ndarray,
        geometry_mask: np.ndarray | None,
        *,
        refinement: float,
    ) -> tuple[np.ndarray, list[str]]:
        """Return a uint8 alpha mask and any warnings."""
