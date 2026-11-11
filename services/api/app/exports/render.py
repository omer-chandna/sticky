"""Prepare a sticker for print or cutting.

`width_mm` and `height_mm` describe the artwork bounding box. A border is
added outside that box. Rotation changes the occupied box and is reported
back so the sheet layout can use the real footprint.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.processing.cutline import CutlineConfig, CutlineResult, generate_cutline


@dataclass
class Appearance:
    width_mm: float = 70
    height_mm: float = 70
    background: str = "transparent"
    background_color: str = "#ffffff"
    border_enabled: bool = False
    border_color: str = "#ffffff"
    border_mm: float = 2
    cut_offset_mm: float = 0
    cut_simplify: float = 0.3
    cut_smooth: float = 0.15
    include_holes: bool = True
    rotation_deg: float = 0
    flip_h: bool = False
    flip_v: bool = False
    dpi: int = 300
    show_cut_guides: bool = False


@dataclass
class RenderedSticker:
    image: np.ndarray
    cutline: CutlineResult
    artwork_width_mm: float
    artwork_height_mm: float
    occupied_width_mm: float
    occupied_height_mm: float
    warnings: list[str] = field(default_factory=list)
    source_pixels: int = 0
    output_pixels: int = 0


def render_sticker(artwork_rgba: np.ndarray, appearance: Appearance) -> RenderedSticker:
    warnings: list[str] = []
    image = artwork_rgba
    if image.shape[2] == 3:
        image = np.dstack([image, np.full(image.shape[:2], 255, np.uint8)])
    source_pixels = int(image.shape[0] * image.shape[1])
    dpi = int(np.clip(appearance.dpi, 72, 600))
    content_w = max(32, int(round(appearance.width_mm / 25.4 * dpi)))
    content_h = max(32, int(round(appearance.height_mm / 25.4 * dpi)))
    # Cap the raster so a huge millimetre value cannot exhaust memory.
    longest = max(content_w, content_h)
    if longest > 4500:
        scale = 4500 / float(longest)
        content_w = max(32, int(round(content_w * scale)))
        content_h = max(32, int(round(content_h * scale)))
        warnings.append("The print raster was capped so the export stays within memory limits. Physical size is unchanged.")
    resized = cv2.resize(image, (content_w, content_h), interpolation=cv2.INTER_LANCZOS4 if longest < image.shape[1] else cv2.INTER_CUBIC)
    if max(content_w, content_h) > max(image.shape[0], image.shape[1]) * 1.15:
        warnings.append(
            "The source photo has fewer pixels than this print size at the chosen DPI. The export is enlarged and does not add real detail."
        )

    alpha = resized[:, :, 3]
    border_px = 0
    if appearance.border_enabled and appearance.border_mm > 0:
        border_px = max(1, int(round(appearance.border_mm / max(appearance.width_mm, 0.1) * content_w)))
    if border_px:
        resized = _add_border(resized, border_px, _hex_to_rgb(appearance.border_color))
    resized = _apply_background(resized, appearance)

    if appearance.flip_h:
        resized = cv2.flip(resized, 1)
    if appearance.flip_v:
        resized = cv2.flip(resized, 0)
    occupied_w_mm = appearance.width_mm + (2 * appearance.border_mm if appearance.border_enabled else 0)
    occupied_h_mm = appearance.height_mm + (2 * appearance.border_mm if appearance.border_enabled else 0)
    if abs(appearance.rotation_deg) % 360 > 0.1:
        resized, rot_w, rot_h = _rotate_bound(resized, appearance.rotation_deg, occupied_w_mm, occupied_h_mm)
        occupied_w_mm, occupied_h_mm = rot_w, rot_h

    offset_px = 0.0
    if abs(appearance.cut_offset_mm) > 0.01:
        offset_px = appearance.cut_offset_mm / max(occupied_w_mm, 0.1) * resized.shape[1]
    cutline = generate_cutline(
        resized[:, :, 3],
        CutlineConfig(
            offset_px=offset_px,
            simplify=appearance.cut_simplify,
            smooth=appearance.cut_smooth,
            include_holes=appearance.include_holes,
        ),
    )
    warnings.extend(cutline.warnings)
    if appearance.show_cut_guides and cutline.path_d:
        resized = _draw_guides(resized)
        warnings.append("Cut guides were drawn onto this export because they were explicitly requested.")
    return RenderedSticker(
        image=resized,
        cutline=cutline,
        artwork_width_mm=round(appearance.width_mm, 3),
        artwork_height_mm=round(appearance.height_mm, 3),
        occupied_width_mm=round(occupied_w_mm, 3),
        occupied_height_mm=round(occupied_h_mm, 3),
        warnings=warnings,
        source_pixels=source_pixels,
        output_pixels=int(resized.shape[0] * resized.shape[1]),
    )


def cutline_svg(
    cutline: CutlineResult,
    *,
    width_mm: float,
    height_mm: float,
    label: str = "Cut outline",
) -> str:
    from app.vectorization.svgutil import sanitize_svg

    pad = 1.0
    view_w = cutline.width + pad * 2
    view_h = cutline.height + pad * 2
    path = cutline.path_d or ""
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:.3f}mm" height="{height_mm:.3f}mm" viewBox="{-pad:.2f} {-pad:.2f} {view_w:.2f} {view_h:.2f}" fill="none" data-sticky-mode="cut">
  <desc>{label}. Closed silhouette for cutting. This file is the cut path, not the printed artwork. Cricut Design Space treats imported SVG paths as cuts unless you change the operation.</desc>
  <path d="{path}" fill="none" stroke="#111111" stroke-width="1" fill-rule="evenodd"/>
</svg>
'''
    return sanitize_svg(svg, allow_embedded_png=False)


def vector_svg_with_size(
    svg: str,
    *,
    width_mm: float,
    height_mm: float,
    view_width: float,
    view_height: float,
) -> str:
    from app.vectorization.svgutil import set_svg_size

    return set_svg_size(
        svg,
        width_mm=width_mm,
        height_mm=height_mm,
        view_width=view_width,
        view_height=view_height,
        description=(
            "Vector reconstruction exported by Sticky. Paths are editable geometry, "
            f"sized {width_mm:.2f} mm by {height_mm:.2f} mm."
        ),
        mode="vector",
    )


def hybrid_svg(
    image_rgba: np.ndarray,
    cutline: CutlineResult,
    *,
    width_mm: float,
    height_mm: float,
) -> str:
    from app.vectorization.svgutil import sanitize_svg

    success, encoded = cv2.imencode(".png", cv2.cvtColor(image_rgba, cv2.COLOR_RGBA2BGRA))
    if not success:
        raise ValueError("Could not encode the hybrid artwork.")
    b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
    height, width = image_rgba.shape[:2]
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width_mm:.3f}mm" height="{height_mm:.3f}mm" viewBox="0 0 {width} {height}" data-sticky-mode="hybrid">
  <desc>Hybrid SVG: embedded raster artwork with a vector cutting outline. Not a full vectorization. The image preserves gradients and fine detail; only the outline is vector geometry.</desc>
  <image href="data:image/png;base64,{b64}" x="0" y="0" width="{width}" height="{height}"/>
  <path id="cutline" d="{cutline.path_d}" fill="none" stroke="none" fill-rule="evenodd"/>
</svg>
'''
    return sanitize_svg(svg, allow_embedded_png=True)


def _add_border(image: np.ndarray, border_px: int, color: tuple[int, int, int]) -> np.ndarray:
    pad = border_px
    padded = cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
    alpha = padded[:, :, 3]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2 + 1, border_px * 2 + 1))
    dilated = cv2.dilate(alpha, kernel, iterations=1)
    ring = (dilated > 127) & (alpha < 250)
    padded[ring, 0] = color[0]
    padded[ring, 1] = color[1]
    padded[ring, 2] = color[2]
    padded[ring, 3] = 255
    # Keep the original artwork fully on top of the ring.
    return padded


def _apply_background(image: np.ndarray, appearance: Appearance) -> np.ndarray:
    if appearance.background != "solid":
        return image
    color = _hex_to_rgb(appearance.background_color)
    alpha = image[:, :, 3]
    binary = np.where(alpha > 12, 255, 0).astype(np.uint8)
    if not appearance.include_holes:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(binary)
        cv2.drawContours(filled, contours, -1, 255, thickness=-1)
        region = filled > 0
    else:
        region = binary > 0
    output = image.copy()
    transparent = region & (output[:, :, 3] < 250)
    output[transparent, 0] = color[0]
    output[transparent, 1] = color[1]
    output[transparent, 2] = color[2]
    output[region, 3] = 255
    return output


def _rotate_bound(
    image: np.ndarray,
    degrees: float,
    width_mm: float,
    height_mm: float,
) -> tuple[np.ndarray, float, float]:
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, -degrees, 1.0)
    radians = np.deg2rad(degrees)
    occupied_w = abs(width * np.cos(radians)) + abs(height * np.sin(radians))
    occupied_h = abs(width * np.sin(radians)) + abs(height * np.cos(radians))
    matrix[0, 2] += occupied_w / 2 - center[0]
    matrix[1, 2] += occupied_h / 2 - center[1]
    rotated = cv2.warpAffine(
        image,
        matrix,
        (max(1, int(round(occupied_w))), max(1, int(round(occupied_h)))),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    scale_w = occupied_w / max(width, 1)
    scale_h = occupied_h / max(height, 1)
    return rotated, width_mm * scale_w, height_mm * scale_h


def _draw_guides(image: np.ndarray) -> np.ndarray:
    output = image.copy()
    height, width = output.shape[:2]
    color = (20, 20, 20, 180)
    length = max(8, int(min(width, height) * 0.04))
    thickness = max(1, int(min(width, height) * 0.004))
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    for x, y in corners:
        x_sign = 1 if x == 0 else -1
        y_sign = 1 if y == 0 else -1
        cv2.line(output, (x, y), (x + x_sign * length, y), color, thickness, lineType=cv2.LINE_AA)
        cv2.line(output, (x, y), (x, y + y_sign * length), color, thickness, lineType=cv2.LINE_AA)
    return output


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        return (255, 255, 255)
    try:
        number = int(text, 16)
    except ValueError:
        return (255, 255, 255)
    return ((number >> 16) & 255, (number >> 8) & 255, number & 255)
