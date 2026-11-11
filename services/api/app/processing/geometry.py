"""Shared geometry helpers.

All public coordinates that cross the API are normalized to the current
image: x and y run from 0 at the top-left to 1 at the bottom-right.
"""

from __future__ import annotations

import base64
import io
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


def denormalize(points: Sequence[Sequence[float]], width: int, height: int) -> np.ndarray:
    array = np.array(points, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("Points must be pairs of x and y.")
    array[:, 0] = np.clip(array[:, 0], 0, 1) * (width - 1)
    array[:, 1] = np.clip(array[:, 1], 0, 1) * (height - 1)
    return array


def normalize_points(points: np.ndarray, width: int, height: int) -> list[tuple[float, float]]:
    result = []
    for x, y in np.asarray(points, dtype=np.float32).reshape(-1, 2):
        result.append((round(float(x) / max(width - 1, 1), 5), round(float(y) / max(height - 1, 1), 5)))
    return result


def order_quad(points: np.ndarray) -> np.ndarray:
    """Order four corners as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    if len({tuple(np.round(point, 3)) for point in ordered}) < 4:
        raise ValueError("Those four corners do not form a usable quadrilateral.")
    return ordered


def polygon_mask(points: Sequence[Sequence[float]], width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    if len(points) < 3:
        return mask
    poly = np.round(denormalize(points, width, height)).astype(np.int32)
    cv2.fillPoly(mask, [poly], 255)
    return mask


def decode_mask(mask_png_base64: str, width: int, height: int) -> np.ndarray:
    """Decode a user brush mask. White keeps, black drops, gray is soft alpha."""
    if len(mask_png_base64) > 18_000_000:
        raise ValueError("The selection mask is too large.")
    try:
        raw = base64.b64decode(mask_png_base64, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("The selection mask could not be read.") from exc
    gray = np.array(image.convert("L"))
    if gray.size == 0:
        raise ValueError("The selection mask is empty.")
    if gray.shape[0] != height or gray.shape[1] != width:
        gray = cv2.resize(gray, (width, height), interpolation=cv2.INTER_LINEAR)
    return gray


def mask_iou(left: np.ndarray, right: np.ndarray) -> float:
    a = left > 127
    b = right > 127
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    return float(np.logical_and(a, b).sum() / union)


def odd(value: int) -> int:
    value = max(1, int(value))
    return value if value % 2 == 1 else value + 1
