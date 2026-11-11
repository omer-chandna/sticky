#!/usr/bin/env python3
"""Create original sample photographs and a real before/after demo.

Run from the repository root:

    services/api/.venv/bin/python examples/generate_samples.py

The pictures are drawn by this script. They are not photographs of existing
commercial stickers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.processing.detect import DetectConfig, detect_stickers  # noqa: E402
from app.processing.pipeline import GeometryInput, PipelineConfig, StickerPipeline  # noqa: E402
from app.processing.restore import RestoreConfig  # noqa: E402
from app.processing.segment import SegmentConfig  # noqa: E402
from app.tests.fixtures import circle_scene, collection_scene, rectangle_scene, star_scene  # noqa: E402


def main() -> None:
    sample_dir = ROOT / "examples" / "samples"
    public_samples = ROOT / "apps" / "web" / "public" / "samples"
    public_demo = ROOT / "apps" / "web" / "public" / "demo"
    for folder in (sample_dir, public_samples, public_demo):
        folder.mkdir(parents=True, exist_ok=True)

    scenes = {
        "rectangle": rectangle_scene()[0],
        "circle": circle_scene()[0],
        "star": star_scene()[0],
        "collection": collection_scene()[0],
    }
    photo = _laptop_photo()
    scenes["laptop"] = photo
    for name, image in scenes.items():
        _save(image, sample_dir / f"{name}.png")

    _save(scenes["rectangle"], public_samples / "single.png")
    _save(scenes["collection"], public_samples / "collection.png")
    _save(photo, public_demo / "before.png")
    restored = _restore(photo)
    _save(restored, public_demo / "after.png")
    print("Wrote samples to examples/samples and apps/web/public")


def _laptop_photo() -> np.ndarray:
    height, width = 900, 1200
    image = np.zeros((height, width, 3), np.uint8)
    for y in range(height):
        shade = 168 + int(18 * np.sin(y / 180))
        image[y, :] = (shade, shade - 2, shade - 6)
    # A soft shadow so the sticker is not a flat paste.
    sticker = np.zeros((420, 560, 3), np.uint8)
    sticker[:, :] = (226, 78, 52)
    cv2.circle(sticker, (280, 200), 92, (255, 244, 230), thickness=-1)
    cv2.circle(sticker, (280, 200), 48, (32, 36, 38), thickness=-1)
    cv2.rectangle(sticker, (70, 300), (490, 332), (255, 244, 230), thickness=-1)
    quad = np.array([[260, 150], [860, 210], [800, 690], [210, 620]], np.float32)
    source = np.array([[0, 0], [559, 0], [559, 419], [0, 419]], np.float32)
    matrix = cv2.getPerspectiveTransform(source, quad)
    warped = cv2.warpPerspective(sticker, matrix, (width, height))
    mask = cv2.warpPerspective(np.full(sticker.shape[:2], 255, np.uint8), matrix, (width, height))
    shadow = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    shadow = cv2.GaussianBlur(shadow, (0, 0), 6)
    image = image.astype(np.float32)
    image -= (shadow.astype(np.float32) * 0.18)[:, :, None]
    image = np.clip(image, 0, 255).astype(np.uint8)
    keep = mask > 128
    image[keep] = warped[keep]
    return image


def _restore(image: np.ndarray) -> np.ndarray:
    detected = detect_stickers(image, DetectConfig(mode="single"))
    polygon = detected.candidates[0].polygon
    quad = detected.candidates[0].quad if detected.candidates[0].perspective_suggested else None
    result = StickerPipeline().run(
        image,
        PipelineConfig(
            geometry=GeometryInput(
                polygon=polygon,
                quad=quad,
                apply_perspective=bool(quad),
            ),
            segment=SegmentConfig(refinement=35, feather=0.4),
            restore=RestoreConfig(cleanup_strength=18, color_correction=12, sharpness=8, edge_smoothness=10),
            max_dimension=1100,
        ),
    )
    return result.image


def _save(image: np.ndarray, path: Path) -> None:
    mode = "RGBA" if image.ndim == 3 and image.shape[2] == 4 else "RGB"
    Image.fromarray(image, mode=mode).save(path, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
