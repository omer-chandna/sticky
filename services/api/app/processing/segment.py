"""Background removal stage.

User brush masks override the automatic mask where the brush is confident:
values above 200 keep a pixel, values below 50 drop it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.segmentation.opencv_backend import OpenCVSegmenter
from app.segmentation.rembg_backend import RembgSegmenter, RembgUnavailable


@dataclass
class SegmentConfig:
    refinement: float = 40
    feather: float = 0
    backend: str = "opencv"
    enable_rembg: bool = False
    # When true, the brush mask is the finished alpha and is not re-segmented.
    authoritative_mask: bool = False


@dataclass
class SegmentResult:
    alpha: np.ndarray
    warnings: list[str] = field(default_factory=list)
    backend: str = "opencv"


def segment_image(
    image_rgb: np.ndarray,
    geometry_mask: np.ndarray | None,
    brush_mask: np.ndarray | None,
    config: SegmentConfig | None = None,
) -> SegmentResult:
    config = config or SegmentConfig()
    if config.authoritative_mask and brush_mask is not None:
        alpha = brush_mask
        if alpha.shape[:2] != image_rgb.shape[:2]:
            alpha = cv2.resize(alpha, (image_rgb.shape[1], image_rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
        alpha = _feather(alpha, config.feather)
        return SegmentResult(
            alpha=alpha,
            warnings=["The edited mask was used without running automatic background removal again."],
            backend="manual",
        )
    backend_name = config.backend
    warnings: list[str] = []
    if backend_name == "rembg":
        if not config.enable_rembg:
            warnings.append(
                "The rembg segmentation backend is turned off. OpenCV segmentation was used instead."
            )
            backend_name = "opencv"
        else:
            try:
                alpha, extra = RembgSegmenter().segment(
                    image_rgb, geometry_mask, refinement=config.refinement
                )
                warnings.extend(extra)
            except RembgUnavailable as exc:
                warnings.append(str(exc))
                alpha, extra = OpenCVSegmenter().segment(
                    image_rgb, geometry_mask, refinement=config.refinement
                )
                warnings.extend(extra)
                backend_name = "opencv"
            else:
                alpha = _apply_brush(alpha, brush_mask)
                alpha = _feather(alpha, config.feather)
                return SegmentResult(alpha=alpha, warnings=warnings, backend="rembg")
    else:
        alpha, extra = OpenCVSegmenter().segment(image_rgb, geometry_mask, refinement=config.refinement)
        warnings.extend(extra)

    alpha = _apply_brush(alpha, brush_mask)
    alpha = _feather(alpha, config.feather)
    return SegmentResult(alpha=alpha, warnings=_unique(warnings), backend=backend_name)


def _apply_brush(alpha: np.ndarray, brush_mask: np.ndarray | None) -> np.ndarray:
    if brush_mask is None:
        return alpha
    if brush_mask.shape[:2] != alpha.shape[:2]:
        brush_mask = cv2.resize(brush_mask, (alpha.shape[1], alpha.shape[0]), interpolation=cv2.INTER_LINEAR)
    painted = brush_mask.copy()
    # Ignore the mid band so an empty gray mask does not wipe the result.
    # The brush UI sends 0 or 255 except along soft brush edges.
    result = alpha.copy()
    result[painted >= 200] = 255
    result[painted <= 40] = 0
    soft = (painted > 40) & (painted < 200)
    result[soft] = np.maximum(result[soft], painted[soft])
    return result


def _feather(alpha: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return alpha
    sigma = float(np.clip(amount, 0, 100)) / 100.0 * 2.2
    if sigma < 0.15:
        return alpha
    blurred = cv2.GaussianBlur(alpha, (0, 0), sigma)
    return blurred


def _unique(warnings: list[str]) -> list[str]:
    seen: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.append(warning)
    return seen
