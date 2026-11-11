"""Optional rembg segmentation backend.

Disabled unless STICKY_ENABLE_REMBG is true and the package is installed.
Sticky does not download model weights during install. The first enabled run
will download the model selected by REMBG_MODEL into the rembg cache.

Reviewed licenses, as of this writing (confirm again before enabling):

- The rembg Python package is MIT licensed.
- The commonly used u2net and isnet-general-use weights shipped by rembg are
  released under the Apache License 2.0 by their authors. They are not
  bundled with Sticky.
- u2net is about 170 MB. silueta and u2netp are smaller. None of them require
  a GPU, but they are much slower than the OpenCV backend on a laptop.

This backend is a fallback for photographs where color and GrabCut fail. It
is not a generative model and it does not redraw artwork.
"""

from __future__ import annotations

import os

import numpy as np


class RembgUnavailable(RuntimeError):
    """rembg was requested but cannot run."""


class RembgSegmenter:
    name = "rembg"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.environ.get("REMBG_MODEL", "u2netp")

    def segment(
        self,
        image_rgb: np.ndarray,
        geometry_mask: np.ndarray | None,
        *,
        refinement: float,
    ) -> tuple[np.ndarray, list[str]]:
        try:
            from rembg import new_session, remove
        except ImportError as exc:
            raise RembgUnavailable(
                "rembg is not installed. Install it separately and set STICKY_ENABLE_REMBG=true. "
                "The OpenCV segmenter does not need it."
            ) from exc
        from PIL import Image

        image = Image.fromarray(image_rgb)
        session = new_session(self.model_name)
        result = remove(image, session=session)
        alpha = np.array(result.convert("RGBA"))[:, :, 3]
        warnings = [
            f"Background removal used the optional rembg model '{self.model_name}'. "
            "Weights are downloaded locally the first time and are not sent to a third-party API."
        ]
        if geometry_mask is not None:
            alpha = np.where(geometry_mask > 0, alpha, 0).astype(np.uint8)
        # refinement slightly tightens or softens the edge
        import cv2

        if refinement > 70:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            alpha = cv2.erode(alpha, kernel, iterations=1)
        return alpha, warnings
