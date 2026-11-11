"""Compare a vector rendering with the raster it came from.

The score is 1 minus the mean absolute RGB error on pixels that are opaque in
either image. It is a guide for the user, not a claim that the vector matches.
"""

from __future__ import annotations

import io

import cairosvg
import numpy as np
from PIL import Image


def rasterize_svg(svg: str, width: int, height: int) -> np.ndarray:
    png = cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=max(1, int(width)),
        output_height=max(1, int(height)),
    )
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    return np.array(image)


def fidelity_score(source_rgba: np.ndarray, svg: str) -> float:
    height, width = source_rgba.shape[:2]
    try:
        rendered = rasterize_svg(svg, width, height)
    except Exception:
        return 0.0
    if rendered.shape[0] != height or rendered.shape[1] != width:
        return 0.0
    source_opaque = source_rgba[:, :, 3] > 128
    rendered_opaque = rendered[:, :, 3] > 128
    mask = source_opaque | rendered_opaque
    if int(mask.sum()) < 16:
        return 0.0
    difference = np.abs(source_rgba[:, :, :3].astype(np.float32) - rendered[:, :, :3].astype(np.float32))
    mae = float(difference[mask].mean()) / 255.0
    # Penalise missing or extra coverage.
    coverage = float(np.logical_and(source_opaque, rendered_opaque).sum()) / float(mask.sum())
    score = (1.0 - mae) * (0.65 + 0.35 * coverage)
    return float(np.clip(score, 0.0, 1.0))
