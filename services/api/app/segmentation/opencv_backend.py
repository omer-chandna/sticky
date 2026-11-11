"""Color-model segmentation with a GrabCut fallback.

White ink is kept when it does not match the surrounding surface. A hole that
shows the same surface as the outside of the sticker stays transparent.
"""

from __future__ import annotations

import cv2
import numpy as np


class OpenCVSegmenter:
    name = "opencv"

    def segment(
        self,
        image_rgb: np.ndarray,
        geometry_mask: np.ndarray | None,
        *,
        refinement: float,
    ) -> tuple[np.ndarray, list[str]]:
        height, width = image_rgb.shape[:2]
        if geometry_mask is None:
            geometry = np.full((height, width), 255, np.uint8)
        else:
            geometry = geometry_mask
            if geometry.shape[:2] != (height, width):
                geometry = cv2.resize(geometry, (width, height), interpolation=cv2.INTER_NEAREST)

        coverage = float((geometry > 0).mean())
        outside = int((geometry == 0).sum())
        # A tight quadrilateral warp fills the frame with the sticker. Sampling the
        # border then would treat the sticker color as the surface and delete it.
        if geometry_mask is not None and (outside < 80 or coverage > 0.9):
            return _apply_frame_mask(geometry), []

        lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        samples, sample_source = _background_samples(lab, geometry)
        median = np.median(samples, axis=0)
        dist = np.linalg.norm(lab - median[None, None, :], axis=2)
        sample_dist = np.linalg.norm(samples - median, axis=1)
        base = float(np.percentile(sample_dist, 90))
        refinement = float(np.clip(refinement, 0, 100))
        # Higher refinement removes more pixels that resemble the surface.
        threshold = max(6.0, base + 4.0) * (0.72 + 0.55 * (refinement / 100.0))
        very_close = dist <= max(4.0, base + 2.0)
        looks_like_foreground = dist > threshold

        kernel_px = int(round(3 + (1.0 - refinement / 100.0) * 10))
        kernel_px = max(3, kernel_px | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_px, kernel_px))
        deep = cv2.erode(geometry, kernel, iterations=1)

        alpha = np.zeros((height, width), np.uint8)
        keep = (geometry > 0) & ~very_close & (looks_like_foreground | (deep > 0))
        alpha[keep] = 255
        alpha[geometry == 0] = 0
        # Surface-colored holes inside the selection stay open.
        alpha[(geometry > 0) & very_close] = 0

        contrast = _mean_contrast(dist, geometry)
        warnings: list[str] = []
        if contrast < 7.5 or (geometry > 0).sum() > 50 and alpha.mean() < 8:
            grab = _grabcut(image_rgb, geometry)
            if grab is not None and 0.02 < (grab > 0).mean() < 0.98:
                # Trust GrabCut on the fringe, but do not delete interior pixels
                # that are unlike the measured surface. That keeps white artwork
                # when the color model already found it.
                interior_keep = (deep > 0) & ~very_close
                alpha = np.where(interior_keep, 255, grab).astype(np.uint8)
                alpha[geometry == 0] = 0
            elif (alpha > 0).mean() < 0.01:
                alpha = geometry.copy()
                warnings.append(
                    "The sticker is hard to separate from the background. The current outline was kept; refine it with the brush if the edges look wrong."
                )

        alpha = _preserve_or_fill_holes(alpha, very_close)
        specks = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, specks, iterations=1)
        alpha = _preserve_or_fill_holes(alpha, very_close)

        if sample_source == "border" and geometry_mask is None:
            warnings.append(
                "No outline was provided, so the photo edges were treated as the surface around the sticker."
            )
        if contrast < 8:
            warnings.append(
                "The sticker is hard to separate from the background. Refine the mask with the brush if the edges look wrong."
            )
        return alpha, _unique(warnings)


def _apply_frame_mask(geometry: np.ndarray) -> np.ndarray:
    return np.where(geometry > 0, 255, 0).astype(np.uint8)


def _background_samples(lab: np.ndarray, geometry: np.ndarray) -> tuple[np.ndarray, str]:
    outside = geometry == 0
    if int(outside.sum()) > 40:
        return lab[outside], "outside"
    height, width = lab.shape[:2]
    border = max(2, int(round(min(height, width) * 0.04)))
    samples = np.concatenate(
        [
            lab[:border].reshape(-1, 3),
            lab[-border:].reshape(-1, 3),
            lab[:, :border].reshape(-1, 3),
            lab[:, -border:].reshape(-1, 3),
        ],
        axis=0,
    )
    return samples, "border"


def _mean_contrast(dist: np.ndarray, geometry: np.ndarray) -> float:
    inside = dist[geometry > 0]
    outside = dist[geometry == 0]
    if inside.size == 0:
        return 0.0
    outside_mean = float(outside.mean()) if outside.size else float(np.percentile(dist, 10))
    return float(inside.mean() - outside_mean)


def _grabcut(image_rgb: np.ndarray, geometry: np.ndarray) -> np.ndarray | None:
    height, width = image_rgb.shape[:2]
    longest = max(height, width)
    scale = 1.0
    work = image_rgb
    work_geom = geometry
    if longest > 700:
        scale = 700 / float(longest)
        size = (max(16, int(round(width * scale))), max(16, int(round(height * scale))))
        work = cv2.resize(image_rgb, size, interpolation=cv2.INTER_AREA)
        work_geom = cv2.resize(geometry, size, interpolation=cv2.INTER_NEAREST)
    if min(work.shape[:2]) < 16:
        return None
    mask = np.full(work.shape[:2], cv2.GC_BGD, np.uint8)
    mask[work_geom > 0] = cv2.GC_PR_FGD
    inner = cv2.erode(work_geom, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    mask[inner > 0] = cv2.GC_FGD
    if not np.any(mask == cv2.GC_FGD) or not np.any(mask == cv2.GC_BGD):
        rect_margin = max(2, int(min(work.shape[:2]) * 0.04))
        mask[:, :] = cv2.GC_BGD
        mask[rect_margin:-rect_margin, rect_margin:-rect_margin] = cv2.GC_PR_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(work, mask, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None
    binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    if scale != 1.0:
        binary = cv2.resize(binary, (width, height), interpolation=cv2.INTER_NEAREST)
    return binary


def _preserve_or_fill_holes(alpha: np.ndarray, very_close: np.ndarray) -> np.ndarray:
    """Keep enclosed holes only when they match the surrounding surface.

    A one-pixel background border keeps the flood fill reliable even when the
    sticker touches the image edge.
    """
    binary = np.where(alpha > 127, 255, 0).astype(np.uint8)
    padded = cv2.copyMakeBorder(binary, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    flood = padded.copy()
    flood_mask = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 128)
    exterior = flood[1:-1, 1:-1] == 128
    holes = (binary == 0) & ~exterior
    filled = alpha.copy()
    # A hole unlike the surface is artwork that should stay opaque.
    filled[holes & ~very_close] = 255
    filled[holes & very_close] = 0
    return filled


def _unique(warnings: list[str]) -> list[str]:
    seen: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.append(warning)
    return seen
