"""Turn an alpha mask into a simplified closed cutting contour.

The outline follows the sticker silhouette, including optional interior holes.
It does not trace every printed color.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class CutlineConfig:
    offset_px: float = 0
    simplify: float = 0.25
    smooth: float = 0.15
    include_holes: bool = True


@dataclass
class CutlineResult:
    path_d: str
    contours: list[np.ndarray]
    holes: int
    closed: bool
    point_count: int
    width: int
    height: int
    warnings: list[str] = field(default_factory=list)


def generate_cutline(alpha: np.ndarray, config: CutlineConfig | None = None) -> CutlineResult:
    config = config or CutlineConfig()
    if alpha.ndim == 3:
        alpha = alpha[:, :, -1]
    height, width = alpha.shape[:2]
    mask = np.where(alpha > 127, 255, 0).astype(np.uint8)
    warnings: list[str] = []

    smooth = float(np.clip(config.smooth, 0, 1))
    if smooth > 0:
        radius = int(round(1 + smooth * 8))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        mask = cv2.GaussianBlur(mask, (0, 0), 0.4 + smooth * 1.4)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

    offset = float(config.offset_px)
    if abs(offset) >= 0.5:
        radius = int(round(abs(offset)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        if offset > 0:
            pad = radius + 2
            padded = cv2.copyMakeBorder(mask, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
            padded = cv2.dilate(padded, kernel, iterations=1)
            mask = padded
            origin = pad
        else:
            mask = cv2.erode(mask, kernel, iterations=1)
            origin = 0
    else:
        origin = 0

    if int((mask > 0).sum()) < 12:
        warnings.append("The cutting outline is empty. Restore the sticker before generating a cut line.")
        return CutlineResult("", [], 0, False, 0, width, height, warnings)

    mode = cv2.RETR_CCOMP if config.include_holes else cv2.RETR_EXTERNAL
    contours, hierarchy = cv2.findContours(mask, mode, cv2.CHAIN_APPROX_NONE)
    if not contours:
        warnings.append("The cutting outline is empty. Restore the sticker before generating a cut line.")
        return CutlineResult("", [], 0, False, 0, width, height, warnings)

    hierarchy = hierarchy[0] if hierarchy is not None else None
    areas = [abs(cv2.contourArea(contour)) for contour in contours]
    outer_index = int(np.argmax(areas))
    selected: list[tuple[np.ndarray, bool]] = []
    for index, contour in enumerate(contours):
        is_hole = bool(hierarchy is not None and hierarchy[index][3] >= 0)
        if index != outer_index and not (config.include_holes and is_hole):
            continue
        if abs(cv2.contourArea(contour)) < 8:
            continue
        simplified = _simplify_contour(contour, config.simplify)
        if origin:
            simplified = simplified - np.array([[[origin, origin]]], dtype=simplified.dtype)
        selected.append((simplified, is_hole and index != outer_index))

    if not selected:
        warnings.append("The cutting outline is empty. Restore the sticker before generating a cut line.")
        return CutlineResult("", [], 0, False, 0, width, height, warnings)

    # Largest contour first so the outer path leads.
    selected.sort(key=lambda item: cv2.contourArea(item[0]), reverse=True)
    paths = []
    point_count = 0
    holes = 0
    contour_list = []
    for contour, is_hole in selected:
        if len(contour) < 3:
            continue
        paths.append(_contour_to_path(contour))
        point_count += len(contour)
        holes += int(is_hole)
        contour_list.append(contour)
    path_d = " ".join(paths)
    if point_count > 1500:
        warnings.append(
            "The cutting outline is very detailed. Increase simplification before importing it into Cricut Design Space."
        )
    return CutlineResult(
        path_d=path_d,
        contours=contour_list,
        holes=holes,
        closed=path_d.endswith("Z") and point_count >= 3,
        point_count=point_count,
        width=width,
        height=height,
        warnings=warnings,
    )


def _simplify_contour(contour: np.ndarray, simplify: float) -> np.ndarray:
    amount = float(np.clip(simplify, 0, 1))
    peri = float(cv2.arcLength(contour, True)) or 1.0
    epsilon = amount * 0.02 * peri
    if epsilon <= 0.2:
        return contour
    approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) < 3:
        return contour
    return approx


def _contour_to_path(contour: np.ndarray) -> str:
    points = contour.reshape(-1, 2)
    commands = [f"M {points[0, 0]:.2f} {points[0, 1]:.2f}"]
    for x, y in points[1:]:
        commands.append(f"L {x:.2f} {y:.2f}")
    commands.append("Z")
    return " ".join(commands)
