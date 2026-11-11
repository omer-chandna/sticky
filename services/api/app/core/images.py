"""Image loading, validation, and encoding.

Uploads are checked by content. Filenames are not trusted. EXIF orientation
is applied once, when the file is stored, so later stages share one coordinate
system.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

pillow_heif.register_heif_opener()

# Refuse images that expand far past the configured budget.
Image.MAX_IMAGE_PIXELS = 80_000_000


class ImageRejected(ValueError):
    """The upload is not a usable photograph."""


@dataclass
class LoadedImage:
    rgb: np.ndarray
    warnings: list[str] = field(default_factory=list)
    source_format: str = "unknown"


_MAGIC_NOTES = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
)


def _looks_like_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _looks_like_heif(data: bytes) -> bool:
    if len(data) < 12 or data[4:8] != b"ftyp":
        return False
    brand = data[8:12]
    return brand in {
        b"heic",
        b"heix",
        b"heif",
        b"mif1",
        b"msf1",
        b"hevc",
        b"hevx",
        b"avif",
    }


def sniff_format(data: bytes) -> str | None:
    for magic, name in _MAGIC_NOTES:
        if data.startswith(magic):
            return name
    if _looks_like_webp(data):
        return "webp"
    if _looks_like_heif(data):
        return "heif"
    return None


def load_image_bytes(data: bytes, *, max_pixels: int, max_bytes: int) -> LoadedImage:
    """Decode a photograph into an RGB or RGBA array in display orientation."""
    if not data:
        raise ImageRejected("The file is empty.")
    if len(data) > max_bytes:
        raise ImageRejected(
            f"This file is larger than the {max_bytes // (1024 * 1024)} MB upload limit."
        )
    sniffed = sniff_format(data)
    if sniffed is None:
        # Still try Pillow. Content that is not an image fails below.
        pass

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                frame_count = int(getattr(image, "n_frames", 1) or 1)
                oriented = ImageOps.exif_transpose(image)
                if oriented is None:
                    raise ImageRejected("This image could not be read.")
                if oriented.mode == "RGBA":
                    array = np.array(oriented)
                elif oriented.mode == "RGB":
                    array = np.array(oriented)
                else:
                    has_alpha = "A" in oriented.getbands() or oriented.mode == "P" and "transparency" in oriented.info
                    array = np.array(oriented.convert("RGBA" if has_alpha else "RGB"))
        except Image.DecompressionBombError as exc:
            raise ImageRejected(
                "This image is larger than Sticky will decode. Resize it and try again."
            ) from exc
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageRejected(
                "Unsupported or corrupted image. Sticky can read JPG, PNG, WebP, and HEIC."
            ) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit

    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ImageRejected("Unsupported or corrupted image. Sticky can read JPG, PNG, WebP, and HEIC.")
    height, width = array.shape[:2]
    if width < 16 or height < 16:
        raise ImageRejected("This image is too small to restore a sticker.")
    if width * height > max_pixels:
        raise ImageRejected("This image is larger than Sticky will decode. Resize it and try again.")

    warnings: list[str] = []
    if frame_count > 1:
        warnings.append("Only the first frame of an animated image was used.")
    source_format = sniffed or "image"
    return LoadedImage(rgb=array, warnings=warnings, source_format=source_format)


def encode_png(array: np.ndarray) -> bytes:
    image = _to_pil(array)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def encode_preview(array: np.ndarray, max_dimension: int) -> bytes:
    image = _to_pil(array)
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    if image.mode == "RGBA":
        image.save(buffer, format="PNG", optimize=True)
    else:
        image.save(buffer, format="JPEG", quality=86, optimize=True)
    return buffer.getvalue()


def downscale(image: np.ndarray, max_dimension: int) -> tuple[np.ndarray, float]:
    """Return a smaller working image and the scale applied to both axes."""
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_dimension:
        return image, 1.0
    scale = max_dimension / float(longest)
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    import cv2

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


def _to_pil(array: np.ndarray) -> Image.Image:
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    if array.ndim == 2:
        return Image.fromarray(array, mode="L")
    channels = array.shape[2]
    if channels == 4:
        return Image.fromarray(array, mode="RGBA")
    if channels == 3:
        return Image.fromarray(array, mode="RGB")
    raise ImageRejected("Could not encode this image.")
