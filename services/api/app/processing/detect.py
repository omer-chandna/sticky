"""Find candidate stickers in a photograph.

The detector combines a border color model with local contrast. It is
deterministic for the same pixels and parameters. When the photograph does
not contain a clear boundary, it returns a low-confidence selection and tells
the caller to use the manual tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.processing.geometry import normalize_points, order_quad


@dataclass
class DetectConfig:
    mode: str = "single"
    min_area_ratio: float = 0.012
    max_candidates: int = 24


@dataclass
class Candidate:
    id: str
    polygon: list[tuple[float, float]]
    bbox: tuple[float, float, float, float]
    quad: list[tuple[float, float]] | None
    confidence: float
    shape: str
    area_ratio: float
    perspective_suggested: bool
    solidity: float = 1.0


@dataclass
class DetectResult:
    candidates: list[Candidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manual_recommended: bool = False
    width: int = 0
    height: int = 0


def detect_stickers(image_rgb: np.ndarray, config: DetectConfig | None = None) -> DetectResult:
    config = config or DetectConfig()
    height, width = image_rgb.shape[:2]
    work = image_rgb
    longest = max(height, width)
    if longest > 1000:
        scale = 1000 / float(longest)
        work = cv2.resize(
            image_rgb,
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    wh, ww = work.shape[:2]
    lab = cv2.cvtColor(work, cv2.COLOR_RGB2LAB).astype(np.float32)
    border = max(2, int(round(min(wh, ww) * 0.04)))
    samples = _border_samples(lab, border)
    median = np.median(samples, axis=0)
    border_dist = np.linalg.norm(lab - median[None, None, :], axis=2)
    sample_dist = np.linalg.norm(samples - median, axis=1)
    base = float(np.percentile(sample_dist, 97))
    thr = max(8.0, base * 2.0 + 5.0)

    local = _local_distance(lab)
    local_thr = max(5.5, float(np.percentile(local, 82)) * 0.85)
    combined = (border_dist > thr) | ((local > local_thr) & (border_dist > max(5.0, base + 1.5)))
    mask = _clean_mask(combined)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(wh * ww)
    min_area = max(80.0, config.min_area_ratio * image_area)
    found: list[Candidate] = []
    for index, contour in enumerate(contours):
        area = float(cv2.contourArea(contour))
        if area < min_area or area > 0.94 * image_area:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        if bw < 8 or bh < 8:
            continue
        if (x <= 1 and x + bw >= ww - 1) or (y <= 1 and y + bh >= wh - 1):
            continue
        region = np.zeros((wh, ww), np.uint8)
        cv2.drawContours(region, [contour], -1, 255, thickness=-1)
        inside = border_dist[region > 0]
        outside = border_dist[region == 0]
        if inside.size == 0:
            continue
        mean_in = float(inside.mean())
        mean_out = float(outside.mean()) if outside.size else 0.0
        contrast = mean_in - mean_out
        if mean_in < thr * 0.55 and contrast < 6:
            continue
        shape, solidity = _classify(contour)
        touch = _border_touch(x, y, bw, bh, ww, wh)
        contrast_score = float(np.clip(contrast / 22.0, 0, 1))
        area_ratio = area / image_area
        area_score = 1.0 if 0.015 <= area_ratio <= 0.62 else 0.55
        confidence = float(
            np.clip(
                0.1 + 0.64 * contrast_score + 0.18 * area_score + 0.08 * min(solidity, 1.0) - 0.28 * touch,
                0.05,
                0.98,
            )
        )
        if contrast < 6:
            confidence = min(confidence, 0.4)
        polygon_px = _simplify(contour, shape)
        polygon = normalize_points(polygon_px, ww, wh)
        quad = None
        perspective = False
        if shape == "rect":
            try:
                quad_px = _quad_from_contour(contour)
                quad = normalize_points(quad_px, ww, wh)
                perspective = True
            except ValueError:
                shape = "irregular"
        bbox = (
            round(x / ww, 5),
            round(y / wh, 5),
            round(bw / ww, 5),
            round(bh / wh, 5),
        )
        found.append(
            Candidate(
                id=f"c{index}",
                polygon=polygon,
                bbox=bbox,
                quad=quad,
                confidence=round(confidence, 4),
                shape=shape,
                area_ratio=round(area_ratio, 5),
                perspective_suggested=perspective,
                solidity=round(float(solidity), 4),
            )
        )

    found.sort(key=lambda item: (-item.confidence, -item.area_ratio, item.bbox[0], item.bbox[1]))
    limit = 5 if config.mode == "single" else config.max_candidates
    found = found[:limit]
    for index, candidate in enumerate(found):
        candidate.id = f"c{index}"

    warnings: list[str] = []
    manual = False
    if not found:
        manual = True
        warnings.append(
            "Automatic detection could not find a clear sticker boundary. Adjust the selection manually."
        )
        inset = 0.03
        polygon = [
            (inset, inset),
            (1 - inset, inset),
            (1 - inset, 1 - inset),
            (inset, 1 - inset),
        ]
        found = [
            Candidate(
                id="c0",
                polygon=polygon,
                bbox=(inset, inset, 1 - 2 * inset, 1 - 2 * inset),
                quad=polygon,
                confidence=0.1,
                shape="irregular",
                area_ratio=round((1 - 2 * inset) ** 2, 5),
                perspective_suggested=False,
                solidity=1.0,
            )
        ]
    else:
        if _touching_regions(mask, found, ww, wh):
            warnings.append(
                "A region may contain touching or overlapping stickers. Split them with the polygon or brush tool if one outline wraps more than one sticker."
            )
        if found[0].confidence < 0.45:
            manual = True
            warnings.append("Detection is uncertain. Adjust the selection before restoring.")

    if float(np.percentile(border_dist, 92)) < 7.5 and (not found or found[0].confidence < 0.5):
        if not any("low contrast" in warning for warning in warnings):
            warnings.append("This photo has low contrast between the sticker and the surface.")
        manual = True

    return DetectResult(
        candidates=found,
        warnings=warnings,
        manual_recommended=manual,
        width=width,
        height=height,
    )


def _border_samples(lab: np.ndarray, border: int) -> np.ndarray:
    return np.concatenate(
        [
            lab[:border, :, :].reshape(-1, 3),
            lab[-border:, :, :].reshape(-1, 3),
            lab[:, :border, :].reshape(-1, 3),
            lab[:, -border:, :].reshape(-1, 3),
        ],
        axis=0,
    )


def _local_distance(lab: np.ndarray) -> np.ndarray:
    height, width = lab.shape[:2]
    small_w = max(40, width // 8)
    small_h = max(40, height // 8)
    small = cv2.resize(lab, (small_w, small_h), interpolation=cv2.INTER_AREA)
    blur = cv2.GaussianBlur(small, (0, 0), 2.4)
    background = cv2.resize(blur, (width, height), interpolation=cv2.INTER_LINEAR)
    return np.linalg.norm(lab - background, axis=2)


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    image = (mask.astype(np.uint8) * 255)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    image = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel, iterations=1)
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel, iterations=2)
    return image


def _classify(contour: np.ndarray) -> tuple[str, float]:
    area = float(cv2.contourArea(contour))
    peri = float(cv2.arcLength(contour, True))
    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull)) or 1.0
    solidity = area / hull_area
    circularity = (4 * np.pi * area / (peri * peri)) if peri > 1 else 0.0
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True) if peri else contour
    rect = cv2.minAreaRect(contour)
    rect_area = float(rect[1][0] * rect[1][1]) or 1.0
    if circularity >= 0.82 and solidity > 0.9:
        return "circle", solidity
    if len(approx) == 4 and cv2.isContourConvex(approx) and area / rect_area > 0.82 and solidity > 0.86:
        return "rect", solidity
    return "irregular", solidity


def _simplify(contour: np.ndarray, shape: str) -> np.ndarray:
    peri = float(cv2.arcLength(contour, True)) or 1.0
    if shape == "circle":
        epsilon = 0.004 * peri
    elif shape == "rect":
        epsilon = 0.015 * peri
    else:
        epsilon = 0.006 * peri
    approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) < 3:
        return contour
    if len(approx) > 100:
        approx = cv2.approxPolyDP(contour, 0.012 * peri, True)
    return approx


def _quad_from_contour(contour: np.ndarray) -> np.ndarray:
    peri = float(cv2.arcLength(contour, True)) or 1.0
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        return order_quad(approx.reshape(4, 2))
    box = cv2.boxPoints(cv2.minAreaRect(contour))
    return order_quad(box)


def _border_touch(x: int, y: int, bw: int, bh: int, width: int, height: int) -> float:
    touch = 0.0
    if x <= 2:
        touch += 0.25
    if y <= 2:
        touch += 0.25
    if x + bw >= width - 2:
        touch += 0.25
    if y + bh >= height - 2:
        touch += 0.25
    return touch


def _touching_regions(mask: np.ndarray, candidates: list[Candidate], width: int, height: int) -> bool:
    if not candidates:
        return False
    eroded = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1)
    count, _ = cv2.connectedComponents((eroded > 0).astype(np.uint8))
    # Background is one label. More components after erosion than candidates
    # means a blob was bridged.
    foreground_components = max(0, count - 1)
    return foreground_components > len(candidates)
