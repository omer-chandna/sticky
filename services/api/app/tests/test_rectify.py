import cv2
import numpy as np

from app.processing.geometry import normalize_points
from app.processing.rectify import rectify_quad
from app.tests.fixtures import perspective_scene


def test_known_quad_restores_the_artwork():
    _scene, artwork, quad = perspective_scene()
    height, width = _scene.shape[:2]
    normalized = normalize_points(quad, width, height)
    rectified = rectify_quad(_scene, normalized)
    resized = cv2.resize(rectified.image, (artwork.shape[1], artwork.shape[0]), interpolation=cv2.INTER_AREA)
    # Ignore a small border where resampling and the replicate border differ.
    center = resized[12:-12, 12:-12].astype(np.float32)
    source = artwork[12:-12, 12:-12].astype(np.float32)
    mae = np.abs(center - source).mean()
    assert mae < 12
    assert rectified.width > 100 and rectified.height > 80


def test_collinear_corners_are_rejected():
    image = np.zeros((200, 200, 3), np.uint8)
    quad = [(0.1, 0.1), (0.2, 0.1), (0.3, 0.1), (0.4, 0.1)]
    try:
        rectify_quad(image, quad)
    except ValueError as exc:
        assert "corner" in str(exc).lower() or "quadrilateral" in str(exc).lower()
    else:
        raise AssertionError("collinear corners should fail")
