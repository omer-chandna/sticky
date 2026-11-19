"""Raster-to-vector conversion through VTracer 0.6.x.

`convert_raw_image_to_svg` is the entry point verified against the installed
0.6.11 wheel (generator comment reports visioncortex VTracer 0.6.4). Transparent
pixels are omitted, so the result is real path geometry rather than an embedded PNG.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import numpy as np
import vtracer
from PIL import Image

from app.core.images import downscale
from app.vectorization.fidelity import fidelity_score
from app.vectorization.redraw import RedrawConfig, flatten_artwork
from app.vectorization.svgutil import count_paths, has_embedded_image, sanitize_svg

# Redraw flattens the sticker into solid inks at 2x before tracing, so it can
# start from more pixels than the other presets without lumpy paths.
REDRAW_MAX_DIMENSION = 1800
# Tuned on flat inks: stacked shapes avoid hairline gaps between regions.
REDRAW_VTRACER = {
    "colormode": "color",
    "hierarchical": "stacked",
    "mode": "spline",
    "filter_speckle": 24,
    "color_precision": 8,
    "layer_difference": 4,
    "corner_threshold": 60,
    "length_threshold": 5.0,
    "max_iterations": 10,
    "splice_threshold": 45,
    "path_precision": 3,
}

# Controls are 0–100 and map onto the VTracer parameters below.
PRESETS: dict[str, dict[str, float]] = {
    "logo": {
        "color_complexity": 62,
        "curve_smoothness": 70,
        "min_region": 28,
        "edge_detail": 58,
        "noise_filtering": 22,
        "path_simplification": 35,
        "binary": 0,
    },
    "illustration": {
        "color_complexity": 74,
        "curve_smoothness": 55,
        "min_region": 16,
        "edge_detail": 70,
        "noise_filtering": 12,
        "path_simplification": 28,
        "binary": 0,
    },
    "detailed": {
        "color_complexity": 92,
        "curve_smoothness": 34,
        "min_region": 4,
        "edge_detail": 90,
        "noise_filtering": 4,
        "path_simplification": 12,
        "binary": 0,
    },
    "monochrome": {
        "color_complexity": 30,
        "curve_smoothness": 66,
        "min_region": 20,
        "edge_detail": 64,
        "noise_filtering": 18,
        "path_simplification": 30,
        "binary": 1,
    },
}


@dataclass
class VectorConfig:
    preset: str = "illustration"
    color_complexity: float | None = None
    curve_smoothness: float | None = None
    min_region: float | None = None
    edge_detail: float | None = None
    noise_filtering: float | None = None
    path_simplification: float | None = None
    max_dimension: int = 1200


@dataclass
class VectorResult:
    svg: str
    path_count: int
    width: int
    height: int
    fidelity: float
    recommend_faithful: bool
    byte_size: int
    preset: str
    parameters: dict[str, float | str]
    warnings: list[str] = field(default_factory=list)


def vectorize_image(image_rgba: np.ndarray, config: VectorConfig | None = None) -> VectorResult:
    config = config or VectorConfig()
    if image_rgba.shape[2] == 3:
        alpha = np.full(image_rgba.shape[:2], 255, np.uint8)
        image_rgba = np.dstack([image_rgba, alpha])
    redraw = config.preset == "redraw"
    working, _scale = downscale(image_rgba, max(config.max_dimension, REDRAW_MAX_DIMENSION) if redraw else config.max_dimension)
    height, width = working.shape[:2]
    if redraw:
        flat = flatten_artwork(working, RedrawConfig())
        trace_source = flat.image
        params: dict[str, object] = dict(REDRAW_VTRACER)
    else:
        trace_source = working
        params = _vtracer_kwargs(_resolve_controls(config))
    buffer = io.BytesIO()
    Image.fromarray(trace_source, mode="RGBA").save(buffer, format="PNG")
    raw_svg = vtracer.convert_raw_image_to_svg(buffer.getvalue(), img_format="png", **params)
    traced_h, traced_w = trace_source.shape[:2]
    raw_svg = _set_viewport(raw_svg, traced_w, traced_h, width, height)
    svg = sanitize_svg(raw_svg, allow_embedded_png=False)
    # Record the mode in a comment the sanitizer keeps only if it is inside XML.
    # The desc element is added by the export step. Here we keep VTracer's svg.
    path_count = count_paths(svg)
    embedded = has_embedded_image(svg)
    score = fidelity_score(working, svg) if path_count else 0.0
    warnings: list[str] = []
    recommend = False
    if embedded or path_count == 0:
        recommend = True
        warnings.append(
            "Vectorization did not produce usable paths. Use Faithful restoration to keep the original artwork."
        )
    elif score < 0.86:
        recommend = True
        warnings.append(
            "Vectorization loses fine detail compared with the cleaned artwork. Faithful restoration is a better match for this sticker."
        )
    if path_count > 1800:
        warnings.append(
            "This vector file has a very high path count. Simplify it, or use Faithful mode, before cutting."
        )
    return VectorResult(
        svg=svg,
        path_count=path_count,
        width=width,
        height=height,
        fidelity=round(score, 4),
        recommend_faithful=recommend,
        byte_size=len(svg.encode("utf-8")),
        preset=config.preset if config.preset in PRESETS or redraw else "custom",
        parameters={**params, "preset": config.preset},
        warnings=warnings,
    )


def _set_viewport(svg: str, traced_w: int, traced_h: int, width: int, height: int) -> str:
    """Give the SVG its traced coordinate system and the working image's display size.

    Redraw traces at 2x for smoother small shapes; the file should still open at
    the restored sticker's size, and the fidelity check renders it at that size.
    """
    start = svg.find("<svg")
    end = svg.find(">", start)
    if start < 0 or end < 0:
        return svg
    tag = svg[start:end]
    tag = re.sub(r'\s(width|height|viewBox)="[^"]*"', "", tag)
    tag += f' viewBox="0 0 {traced_w} {traced_h}" width="{width}" height="{height}"'
    return svg[:start] + tag + svg[end:]


def _resolve_controls(config: VectorConfig) -> dict[str, float]:
    base = dict(PRESETS.get(config.preset, PRESETS["illustration"]))
    for name in (
        "color_complexity",
        "curve_smoothness",
        "min_region",
        "edge_detail",
        "noise_filtering",
        "path_simplification",
    ):
        value = getattr(config, name)
        if value is not None:
            base[name] = float(np.clip(value, 0, 100))
    return base


def _vtracer_kwargs(controls: dict[str, float]) -> dict[str, object]:
    """Map 0–100 controls onto the VTracer 0.6 ranges.

    The neutral point of each control is close to VTracer's own defaults
    (color precision 6, layer difference 16, speckle 4, corner 60, length 4).
    Cutout paths do not rely on stacking order, so individual shapes stay editable.
    """
    complexity = controls["color_complexity"] / 100.0
    smooth = controls["curve_smoothness"] / 100.0
    detail = controls["edge_detail"] / 100.0
    noise = controls["noise_filtering"] / 100.0
    region = controls["min_region"] / 100.0
    simplify = controls["path_simplification"] / 100.0
    filter_speckle = int(round(1 + noise * 6 + region * 5))
    color_precision = int(round(2 + complexity * 6))
    layer_difference = int(round(36 - complexity * 28))
    length_threshold = float(np.clip(7.2 - detail * 6.0, 1.0, 8.5))
    corner_threshold = int(round(20 + smooth * 80))
    path_precision = int(round(8 - simplify * 5))
    return {
        "colormode": "binary" if controls.get("binary", 0) >= 0.5 else "color",
        "hierarchical": "cutout",
        "mode": "spline" if smooth >= 0.25 else "polygon",
        "filter_speckle": int(np.clip(filter_speckle, 1, 24)),
        "color_precision": int(np.clip(color_precision, 2, 8)),
        "layer_difference": int(np.clip(layer_difference, 6, 48)),
        "corner_threshold": int(np.clip(corner_threshold, 15, 110)),
        "length_threshold": length_threshold,
        "max_iterations": 10,
        "splice_threshold": int(round(25 + smooth * 40)),
        "path_precision": int(np.clip(path_precision, 2, 8)),
    }
