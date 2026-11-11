"""Synthetic photographs with known geometry.

Nothing in here is a real brand or a copied sticker. Shapes are drawn so the
tests know the expected mask.
"""

from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageDraw


def rgb_canvas(width: int, height: int, color: tuple[int, int, int]) -> np.ndarray:
    image = np.zeros((height, width, 3), np.uint8)
    image[:, :] = color
    return image


def rectangle_scene() -> tuple[np.ndarray, np.ndarray]:
    image = rgb_canvas(800, 600, (176, 178, 182))
    x0, y0, x1, y1 = 180, 130, 620, 470
    cv2.rectangle(image, (x0, y0), (x1, y1), (214, 48, 42), thickness=-1)
    cv2.circle(image, (400, 300), 70, (255, 255, 255), thickness=-1)
    cv2.rectangle(image, (250, 270), (330, 310), (25, 25, 25), thickness=-1)
    mask = np.zeros((600, 800), np.uint8)
    cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)
    return image, mask


def circle_scene() -> tuple[np.ndarray, np.ndarray]:
    image = rgb_canvas(640, 640, (168, 170, 166))
    cv2.circle(image, (320, 320), 180, (32, 96, 210), thickness=-1)
    cv2.circle(image, (320, 320), 70, (255, 248, 230), thickness=-1)
    mask = np.zeros((640, 640), np.uint8)
    cv2.circle(mask, (320, 320), 180, 255, thickness=-1)
    return image, mask


def star_scene() -> tuple[np.ndarray, np.ndarray]:
    image = rgb_canvas(700, 700, (188, 184, 176))
    center = np.array([350, 350], np.float32)
    points = []
    for index in range(10):
        angle = -np.pi / 2 + index * (2 * np.pi / 10)
        radius = 210 if index % 2 == 0 else 90
        points.append(center + radius * np.array([np.cos(angle), np.sin(angle)]))
    poly = np.round(np.array(points)).astype(np.int32)
    cv2.fillPoly(image, [poly], (24, 150, 96))
    mask = np.zeros((700, 700), np.uint8)
    cv2.fillPoly(mask, [poly], 255)
    return image, mask


def collection_scene() -> tuple[np.ndarray, list[np.ndarray]]:
    image = rgb_canvas(1000, 720, (150, 152, 158))
    masks = []
    specs = [
        ("rect", (80, 80, 300, 280), (210, 64, 48)),
        ("circle", (520, 180, 110), (40, 90, 190)),
        ("rect", (680, 360, 940, 620), (230, 180, 40)),
    ]
    for kind, geom, color in specs:
        mask = np.zeros(image.shape[:2], np.uint8)
        if kind == "rect":
            x0, y0, x1, y1 = geom
            cv2.rectangle(image, (x0, y0), (x1, y1), color, thickness=-1)
            cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)
            cv2.circle(image, ((x0 + x1) // 2, (y0 + y1) // 2), 30, (255, 255, 255), thickness=-1)
        else:
            cx, cy, radius = geom
            cv2.circle(image, (cx, cy), radius, color, thickness=-1)
            cv2.circle(mask, (cx, cy), radius, 255, thickness=-1)
        masks.append(mask)
    return image, masks


def perspective_scene() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    artwork = np.zeros((300, 420, 3), np.uint8)
    artwork[:, :] = (200, 48, 36)
    cv2.rectangle(artwork, (36, 36), (384, 264), (255, 255, 255), thickness=-1)
    cv2.rectangle(artwork, (70, 120), (200, 160), (20, 20, 20), thickness=-1)
    background = rgb_canvas(900, 700, (164, 166, 170))
    quad = np.array([[210, 90], [690, 150], [640, 560], [160, 470]], dtype=np.float32)
    return _paste_quad(background, artwork, quad), artwork, quad


def white_artwork_scene() -> tuple[np.ndarray, np.ndarray]:
    image = rgb_canvas(640, 520, (36, 40, 48))
    x0, y0, x1, y1 = 150, 90, 500, 420
    cv2.rectangle(image, (x0, y0), (x1, y1), (246, 246, 246), thickness=-1)
    cv2.circle(image, (320, 250), 55, (210, 48, 42), thickness=-1)
    cv2.rectangle(image, (220, 180), (270, 210), (20, 20, 20), thickness=-1)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)
    return image, mask


def donut_scene() -> tuple[np.ndarray, np.ndarray]:
    image = rgb_canvas(520, 520, (120, 124, 130))
    cv2.circle(image, (260, 260), 160, (190, 48, 72), thickness=-1)
    cv2.circle(image, (260, 260), 70, (120, 124, 130), thickness=-1)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.circle(mask, (260, 260), 160, 255, thickness=-1)
    cv2.circle(mask, (260, 260), 70, 0, thickness=-1)
    return image, mask


def low_contrast_scene() -> np.ndarray:
    image = rgb_canvas(480, 360, (150, 150, 150))
    cv2.rectangle(image, (140, 90), (340, 250), (156, 156, 156), thickness=-1)
    return image


def gradient_collection() -> np.ndarray:
    height, width = 640, 960
    ramp = np.linspace(90, 210, width, dtype=np.float32)
    image = np.repeat(ramp[None, :, None], height, axis=0)
    image = np.repeat(image, 3, axis=2)
    image = np.clip(image + 8, 0, 255).astype(np.uint8)
    cv2.rectangle(image, (80, 70), (280, 250), (200, 40, 40), thickness=-1)
    cv2.circle(image, (620, 360), 110, (30, 90, 200), thickness=-1)
    return image


def glare_scene() -> np.ndarray:
    image, _mask = rectangle_scene()
    overlay = image.copy()
    cv2.circle(overlay, (400, 220), 50, (255, 255, 255), thickness=-1)
    return cv2.addWeighted(image, 0.2, overlay, 0.8, 0)


def flat_logo() -> np.ndarray:
    image = np.zeros((220, 360, 4), np.uint8)
    cv2.rectangle(image, (20, 20), (340, 200), (220, 40, 40, 255), thickness=-1)
    cv2.circle(image, (180, 110), 48, (255, 255, 255, 255), thickness=-1)
    cv2.rectangle(image, (70, 90), (110, 130), (20, 20, 20, 255), thickness=-1)
    return image


def gradient_badge() -> np.ndarray:
    width, height = 280, 180
    canvas = np.zeros((height, width, 4), np.uint8)
    for x in range(width):
        t = x / max(width - 1, 1)
        color = (
            int(220 * (1 - t) + 40 * t),
            int(40 * (1 - t) + 90 * t),
            int(40 * (1 - t) + 210 * t),
            255,
        )
        canvas[:, x] = color
    return canvas


def png_bytes(image: np.ndarray) -> bytes:
    mode = "RGBA" if image.shape[2] == 4 else "RGB"
    buffer = io.BytesIO()
    Image.fromarray(image, mode=mode).save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_with_orientation(image: np.ndarray) -> bytes:
    pil = Image.fromarray(image, mode="RGB")
    exif = Image.Exif()
    exif[274] = 6
    buffer = io.BytesIO()
    pil.save(buffer, format="JPEG", quality=95, exif=exif)
    return buffer.getvalue()


def _paste_quad(background: np.ndarray, artwork: np.ndarray, quad: np.ndarray) -> np.ndarray:
    height, width = artwork.shape[:2]
    source = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(source, quad.astype(np.float32))
    warped = cv2.warpPerspective(artwork, matrix, (background.shape[1], background.shape[0]))
    mask = cv2.warpPerspective(np.full((height, width), 255, np.uint8), matrix, (background.shape[1], background.shape[0]))
    output = background.copy()
    keep = mask > 128
    output[keep] = warped[keep]
    return output
