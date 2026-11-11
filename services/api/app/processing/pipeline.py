"""Composable sticker pipeline.

Stages always start from the source image and the current geometry. They do
not re-filter a previous filtered result, so slider changes do not compound.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

from app.processing.cutline import CutlineConfig, CutlineResult, generate_cutline
from app.processing.detect import DetectConfig, DetectResult, detect_stickers
from app.processing.geometry import decode_mask, denormalize, polygon_mask
from app.processing.rectify import rectify_quad, warp_mask
from app.processing.restore import RestoreConfig, RestoreResult, restore_image
from app.processing.segment import SegmentConfig, SegmentResult, segment_image
from app.vectorization.vtracer_backend import VectorConfig, VectorResult, vectorize_image


@dataclass
class GeometryInput:
    polygon: list[tuple[float, float]] | None = None
    quad: list[tuple[float, float]] | None = None
    apply_perspective: bool = False
    mask_png_base64: str | None = None
    authoritative_mask: bool = False


@dataclass
class PipelineConfig:
    geometry: GeometryInput = field(default_factory=GeometryInput)
    segment: SegmentConfig = field(default_factory=SegmentConfig)
    restore: RestoreConfig = field(default_factory=RestoreConfig)
    max_dimension: int = 1400


@dataclass
class PipelineResult:
    image: np.ndarray
    before: np.ndarray
    alpha: np.ndarray
    cutline: CutlineResult
    warnings: list[str] = field(default_factory=list)
    transform: dict = field(default_factory=dict)
    original_width: int = 0
    original_height: int = 0
    segment_backend: str = "opencv"


class StickerPipeline:
    """Processing entry points shared by the API and tests."""

    def detect(self, image: np.ndarray, config: DetectConfig | None = None) -> DetectResult:
        return detect_stickers(_rgb(image), config)

    def rectify(self, image: np.ndarray, quad: list[tuple[float, float]]):
        return rectify_quad(_rgb(image), quad)

    def segment(
        self,
        image: np.ndarray,
        geometry_mask: np.ndarray | None,
        brush_mask: np.ndarray | None,
        config: SegmentConfig | None = None,
    ) -> SegmentResult:
        return segment_image(_rgb(image), geometry_mask, brush_mask, config)

    def restore(self, image: np.ndarray, mask: np.ndarray, config: RestoreConfig | None = None) -> RestoreResult:
        return restore_image(_rgb(image), mask, config)

    def vectorize(self, image: np.ndarray, config: VectorConfig | None = None) -> VectorResult:
        rgba = image if image.shape[2] == 4 else np.dstack([image, np.full(image.shape[:2], 255, np.uint8)])
        return vectorize_image(rgba, config)

    def generate_cutline(self, mask: np.ndarray, config: CutlineConfig | None = None) -> CutlineResult:
        return generate_cutline(mask, config)

    def run(self, image: np.ndarray, config: PipelineConfig | None = None) -> PipelineResult:
        config = config or PipelineConfig()
        original = image
        original_height, original_width = original.shape[:2]
        rgb = _rgb(original)
        working, _scale = _limit(rgb, config.max_dimension)
        prepared, geometry_mask, brush_mask, transform, prep_warnings = prepare_geometry(working, config.geometry)
        segmented = self.segment(
            prepared,
            geometry_mask,
            brush_mask,
            SegmentConfig(
                refinement=config.segment.refinement,
                feather=0,
                backend=config.segment.backend,
                enable_rembg=config.segment.enable_rembg,
                authoritative_mask=config.geometry.authoritative_mask,
            ),
        )
        before = np.dstack(
            [
                prepared if prepared.shape[2] == 3 else prepared[:, :, :3],
                segmented.alpha,
            ]
        )
        restored = self.restore(prepared, segmented.alpha, config.restore)
        cutline = self.generate_cutline(
            restored.image[:, :, 3],
            CutlineConfig(simplify=0.2, smooth=min(0.4, config.restore.edge_smoothness / 100), include_holes=True),
        )
        warnings = [*prep_warnings, *segmented.warnings, *restored.warnings]
        return PipelineResult(
            image=restored.image,
            before=before,
            alpha=restored.image[:, :, 3],
            cutline=cutline,
            warnings=_unique(warnings),
            transform=transform,
            original_width=original_width,
            original_height=original_height,
            segment_backend=segmented.backend,
        )


def prepare_geometry(
    image: np.ndarray,
    geometry: GeometryInput,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None, dict, list[str]]:
    """Crop or rectify, and return masks in the output coordinate system."""
    rgb = _rgb(image)
    height, width = rgb.shape[:2]
    warnings: list[str] = []
    brush = None
    if geometry.mask_png_base64:
        brush = decode_mask(geometry.mask_png_base64, width, height)

    if geometry.apply_perspective and geometry.quad and len(geometry.quad) == 4:
        try:
            rectified = rectify_quad(rgb, geometry.quad)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        warnings.extend(rectified.warnings)
        matrix = np.array(rectified.matrix, dtype=np.float32)
        poly_mask = None
        if geometry.polygon and len(geometry.polygon) >= 3:
            source_mask = polygon_mask(geometry.polygon, width, height)
            poly_mask = warp_mask(source_mask, matrix, rectified.width, rectified.height)
        if brush is not None:
            brush = warp_mask(brush, matrix, rectified.width, rectified.height)
        transform = {
            "type": "perspective",
            "matrix": rectified.matrix,
            "output_width": rectified.width,
            "output_height": rectified.height,
        }
        return rectified.image, poly_mask, brush, transform, warnings

    if geometry.polygon and len(geometry.polygon) >= 3:
        poly = np.round(denormalize(geometry.polygon, width, height)).astype(np.int32)
        x, y, box_w, box_h = cv2.boundingRect(poly)
        pad = int(max(box_w, box_h) * 0.03) + 2
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(width, x + box_w + pad)
        y1 = min(height, y + box_h + pad)
        crop = rgb[y0:y1, x0:x1]
        shifted = poly - np.array([x0, y0])
        poly_mask = np.zeros(crop.shape[:2], np.uint8)
        cv2.fillPoly(poly_mask, [shifted], 255)
        if brush is not None:
            brush = brush[y0:y1, x0:x1]
        transform = {
            "type": "crop",
            "origin": [int(x0), int(y0)],
            "output_width": int(x1 - x0),
            "output_height": int(y1 - y0),
        }
        return crop, poly_mask, brush, transform, warnings

    transform = {"type": "identity", "output_width": width, "output_height": height}
    if geometry.apply_perspective:
        warnings.append(
            "Perspective correction was requested without four corners, so the photo was left as taken."
        )
    return rgb, None, brush, transform, warnings


def encode_mask_png(mask: np.ndarray) -> str:
    image = Image.fromarray(mask.astype(np.uint8), mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image


def _limit(image: np.ndarray, max_dimension: int) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_dimension:
        return image, 1.0
    scale = max_dimension / float(longest)
    resized = cv2.resize(
        image,
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def _unique(warnings: list[str]) -> list[str]:
    seen: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.append(warning)
    return seen
