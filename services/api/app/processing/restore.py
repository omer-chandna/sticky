"""Non-generative cleanup.

Adjustments are limited so a slider cannot posterize, oversharpen, or invent
texture. Illumination leveling (CLAHE) runs only when asked, or when cleanup
is high and the sticker lighting is visibly uneven.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class RestoreConfig:
    cleanup_strength: float = 30
    edge_smoothness: float = 15
    color_correction: float = 0
    sharpness: float = 10
    brightness: float = 0
    contrast: float = 0
    saturation: float = 0
    exposure: float = 0
    denoise: float = 0
    white_balance: float = 0
    clahe: bool = False


@dataclass
class RestoreResult:
    image: np.ndarray
    warnings: list[str] = field(default_factory=list)
    illumination_applied: bool = False


def restore_image(image_rgb: np.ndarray, alpha: np.ndarray, config: RestoreConfig | None = None) -> RestoreResult:
    config = config or RestoreConfig()
    warnings: list[str] = []
    rgb = image_rgb[:, :, :3].astype(np.float32)
    if alpha.shape[:2] != rgb.shape[:2]:
        alpha = cv2.resize(alpha, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    alpha_u8 = np.clip(alpha, 0, 255).astype(np.uint8)
    foreground = alpha_u8 > 128

    color_amount = _unit(config.color_correction)
    white_balance_amount = max(color_amount, _unit(config.white_balance))
    if white_balance_amount > 0:
        balanced = _gray_world(rgb, foreground)
        rgb = _blend(balanced, rgb, white_balance_amount)

    rgb = _apply_exposure(rgb, config.exposure)
    rgb = _apply_brightness_contrast(rgb, foreground, config.brightness, config.contrast)
    rgb = _apply_saturation(rgb, config.saturation)

    denoise_amount = max(_unit(config.denoise), _unit(config.cleanup_strength) * 0.65)
    if denoise_amount > 0.05:
        sigma = 4 + denoise_amount * 22
        rgb_u8 = np.clip(rgb, 0, 255).astype(np.uint8)
        filtered = cv2.bilateralFilter(rgb_u8, d=5, sigmaColor=sigma, sigmaSpace=sigma)
        # Keep the bilateral result mild: cleanup should not turn type into plastic.
        rgb = _blend(filtered.astype(np.float32), rgb, min(0.85, denoise_amount))

    illumination_applied = False
    if config.clahe or config.cleanup_strength >= 85:
        if _lighting_is_uneven(rgb, foreground) or config.clahe:
            before_std = _luminance_std(rgb, foreground)
            leveled = _flatten_illumination(rgb, foreground)
            after_std = _luminance_std(leveled, foreground)
            # Only keep the correction when it actually flattens the lighting.
            # CLAHE was tried on smooth ramps and increased local variance, so
            # this is a bounded division by a blurred luminance field instead.
            if config.clahe or after_std < before_std * 0.92:
                rgb = leveled
                illumination_applied = True
            elif config.clahe:
                warnings.append("Lighting already looks even, so strong illumination correction was skipped.")

    sharp = _unit(config.sharpness)
    if sharp > 0:
        rgb_u8 = np.clip(rgb, 0, 255).astype(np.uint8)
        blurred = cv2.GaussianBlur(rgb_u8, (0, 0), 1.1)
        amount = sharp * 0.75
        sharpened = cv2.addWeighted(rgb_u8, 1 + amount, blurred, -amount, 0)
        rgb = sharpened.astype(np.float32)

    edge = _unit(config.edge_smoothness)
    if edge > 0:
        sigma = 0.2 + edge * 1.6
        alpha_u8 = cv2.GaussianBlur(alpha_u8, (0, 0), sigma)

    warnings.extend(_quality_warnings(image_rgb, foreground))
    rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), alpha_u8])
    return RestoreResult(image=rgba, warnings=warnings, illumination_applied=illumination_applied)


def _unit(value: float) -> float:
    return float(np.clip(value, 0, 100)) / 100.0


def _blend(adjusted: np.ndarray, original: np.ndarray, amount: float) -> np.ndarray:
    return adjusted * amount + original * (1 - amount)


def _gray_world(rgb: np.ndarray, foreground: np.ndarray) -> np.ndarray:
    pixels = rgb[foreground] if int(foreground.sum()) > 20 else rgb.reshape(-1, 3)
    means = pixels.mean(axis=0) + 1e-3
    gray = float(means.mean())
    scale = gray / means
    # Limit the correction so a genuinely warm sticker is not forced to gray.
    scale = np.clip(scale, 0.75, 1.35)
    return np.clip(rgb * scale.reshape(1, 1, 3), 0, 255)


def _apply_exposure(rgb: np.ndarray, exposure: float) -> np.ndarray:
    stops = float(np.clip(exposure, -100, 100)) / 100.0 * 1.25
    if abs(stops) < 0.01:
        return rgb
    return np.clip(rgb * (2 ** stops), 0, 255)


def _apply_brightness_contrast(
    rgb: np.ndarray,
    foreground: np.ndarray,
    brightness: float,
    contrast: float,
) -> np.ndarray:
    bright = float(np.clip(brightness, -100, 100)) / 100.0 * 40.0
    contrast_value = float(np.clip(contrast, -100, 100)) / 100.0
    gain = 1 + contrast_value * 0.45
    pivot_pixels = rgb[foreground] if int(foreground.sum()) > 20 else rgb.reshape(-1, 3)
    pivot = float(pivot_pixels.mean())
    adjusted = (rgb - pivot) * gain + pivot + bright
    return np.clip(adjusted, 0, 255)


def _apply_saturation(rgb: np.ndarray, saturation: float) -> np.ndarray:
    amount = float(np.clip(saturation, -100, 100)) / 100.0
    if abs(amount) < 0.01:
        return rgb
    gain = float(np.clip(1 + amount * 0.8, 0, 1.8))
    uint8 = np.clip(rgb, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * gain, 0, 255)
    back = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return back.astype(np.float32)


def _lighting_is_uneven(rgb: np.ndarray, foreground: np.ndarray) -> bool:
    gray = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB)[:, :, 0]
    values = gray[foreground] if int(foreground.sum()) > 20 else gray.reshape(-1)
    if values.size < 20:
        return False
    return float(values.std()) > 28


def _luminance_std(rgb: np.ndarray, foreground: np.ndarray) -> float:
    gray = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB)[:, :, 0]
    values = gray[foreground] if int(foreground.sum()) > 20 else gray.reshape(-1)
    if values.size == 0:
        return 0.0
    return float(values.std())


def _flatten_illumination(rgb: np.ndarray, foreground: np.ndarray) -> np.ndarray:
    """Retinex-style leveling. The scale is clamped so colors cannot blow out."""
    gray = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    sigma = max(8.0, min(rgb.shape[:2]) * 0.15)
    blur = cv2.GaussianBlur(gray, (0, 0), sigma)
    blur = np.clip(blur, 8.0, None)
    if int(foreground.sum()) > 20:
        target = float(np.median(gray[foreground]))
    else:
        target = float(np.median(gray))
    target = float(np.clip(target, 40, 210))
    scale = np.clip(target / blur, 0.6, 1.7)
    return np.clip(rgb * scale[:, :, None], 0, 255)


def _quality_warnings(image_rgb: np.ndarray, foreground: np.ndarray) -> list[str]:
    gray = cv2.cvtColor(image_rgb[:, :, :3], cv2.COLOR_RGB2GRAY)
    if int(foreground.sum()) > 30:
        sample = gray[foreground]
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = float(lap[foreground].var())
    else:
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    warnings = []
    if sharpness < 18:
        warnings.append(
            "This photo looks blurry. Sticky cannot invent missing detail — a sharper photograph will produce a better sticker."
        )
    if _has_specular_hotspot(gray, foreground):
        warnings.append(
            "Bright reflections cover part of this sticker. A more direct photo without glare will reconstruct it more faithfully."
        )
    return warnings


def _has_specular_hotspot(gray: np.ndarray, foreground: np.ndarray) -> bool:
    """A glare spot is a small region much brighter than its neighborhood.

    Flat white artwork is bright, but it is not brighter than the white around
    it, so it is not reported as a reflection.
    """
    local = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 12)
    hotspot = (gray.astype(np.float32) > 245) & ((gray.astype(np.float32) - local) > 35) & foreground
    # A flat white shape only lights up in a thin ring. A reflection is a filled blob.
    core = cv2.erode(hotspot.astype(np.uint8) * 255, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats((core > 0).astype(np.uint8))
    total = float(gray.size) or 1.0
    for index in range(1, count):
        area = float(stats[index, cv2.CC_STAT_AREA])
        box = float(stats[index, cv2.CC_STAT_WIDTH] * stats[index, cv2.CC_STAT_HEIGHT]) or 1.0
        solidity = area / box
        fraction = area / total
        if solidity > 0.45 and 0.0005 < fraction < 0.04:
            return True
    return False
