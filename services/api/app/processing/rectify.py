"""Planar perspective correction.

A quadrilateral sticker is warped to a front-facing rectangle using the edge
lengths of the selected corners, so the aspect ratio follows the photograph
instead of a fixed page. Irregular silhouettes are not forced into rectangles;
callers pass a polygon and crop instead of warping.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.processing.geometry import denormalize, order_quad


@dataclass
class RectifyResult:
    image: np.ndarray
    matrix: list[list[float]]
    width: int
    height: int
    warnings: list[str] = field(default_factory=list)


def rectify_quad(image: np.ndarray, quad: list[tuple[float, float]]) -> RectifyResult:
    if len(quad) != 4:
        raise ValueError("Perspective correction needs exactly four corners.")
    height, width = image.shape[:2]
    source = order_quad(denormalize(quad, width, height))
    top = float(np.linalg.norm(source[1] - source[0]))
    bottom = float(np.linalg.norm(source[2] - source[3]))
    left = float(np.linalg.norm(source[3] - source[0]))
    right = float(np.linalg.norm(source[2] - source[1]))
    out_w = int(round(max(top, bottom)))
    out_h = int(round(max(left, right)))
    out_w = int(np.clip(out_w, 16, 8000))
    out_h = int(np.clip(out_h, 16, 8000))
    if min(top, bottom, left, right) < 8:
        raise ValueError("Those corners are too close together to correct perspective.")
    destination = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(
        image,
        matrix,
        (out_w, out_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    warnings: list[str] = []
    ratio = (out_w / out_h) if out_h else 1
    if ratio > 8 or ratio < 0.125:
        warnings.append(
            "The corrected sticker is extremely wide or tall. Move the corners if this does not match the real sticker."
        )
    return RectifyResult(
        image=warped,
        matrix=matrix.astype(float).tolist(),
        width=out_w,
        height=out_h,
        warnings=warnings,
    )


def warp_mask(mask: np.ndarray, matrix: np.ndarray, width: int, height: int) -> np.ndarray:
    return cv2.warpPerspective(mask, matrix, (width, height), flags=cv2.INTER_LINEAR, borderValue=0)
