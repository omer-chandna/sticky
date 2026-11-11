import cv2
import numpy as np

from app.processing.restore import RestoreConfig, restore_image


def test_brightness_increases_luminance_and_stays_in_range():
    image = np.full((80, 80, 3), 80, np.uint8)
    alpha = np.full((80, 80), 255, np.uint8)
    result = restore_image(image, alpha, RestoreConfig(cleanup_strength=0, color_correction=0, sharpness=0, brightness=60))
    assert result.image[:, :, :3].mean() > image.mean() + 10
    assert result.image[:, :, :3].max() <= 255


def test_same_settings_are_deterministic():
    rng = np.random.default_rng(3)
    image = rng.integers(0, 255, size=(64, 70, 3), dtype=np.uint8)
    alpha = np.full((64, 70), 255, np.uint8)
    config = RestoreConfig(cleanup_strength=20, color_correction=30, sharpness=15, brightness=5, contrast=10)
    first = restore_image(image, alpha, config).image
    second = restore_image(image, alpha, config).image
    assert np.array_equal(first, second)


def test_blur_and_glare_warnings():
    blurry = np.full((90, 90, 3), 140, np.uint8)
    alpha = np.full((90, 90), 255, np.uint8)
    blur_result = restore_image(blurry, alpha, RestoreConfig(cleanup_strength=0, sharpness=0, color_correction=0))
    assert any("blurry" in warning.lower() for warning in blur_result.warnings)

    glare = np.full((120, 120, 3), 90, np.uint8)
    cv2.circle(glare, (70, 48), 7, (255, 255, 255), thickness=-1)
    glare_result = restore_image(glare, np.full((120, 120), 255, np.uint8), RestoreConfig(cleanup_strength=0, sharpness=0, color_correction=0))
    assert any("reflection" in warning.lower() or "glare" in warning.lower() for warning in glare_result.warnings)

    artwork = np.full((120, 120, 3), 40, np.uint8)
    cv2.circle(artwork, (60, 60), 36, (255, 255, 255), thickness=-1)
    white_result = restore_image(artwork, np.full((120, 120), 255, np.uint8), RestoreConfig(cleanup_strength=0, sharpness=0, color_correction=0))
    assert not any("reflection" in warning.lower() or "glare" in warning.lower() for warning in white_result.warnings)


def test_clahe_reduces_a_strong_lighting_ramp():
    width = 180
    ramp = np.linspace(40, 220, width).astype(np.uint8)
    image = np.zeros((80, width, 3), np.uint8)
    image[:, :, 0] = ramp
    image[:, :, 1] = ramp
    image[:, :, 2] = ramp
    alpha = np.full(image.shape[:2], 255, np.uint8)
    before = image[:, :, 0].std()
    result = restore_image(
        image,
        alpha,
        RestoreConfig(cleanup_strength=0, color_correction=0, sharpness=0, clahe=True),
    )
    after = result.image[:, :, 0].std()
    assert result.illumination_applied is True
    assert after < before * 0.85
