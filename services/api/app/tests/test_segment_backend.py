import numpy as np

from app.processing import segment as segment_module
from app.processing.segment import SegmentConfig, segment_image as segment


def _image() -> np.ndarray:
    image = np.full((120, 160, 3), 40, np.uint8)
    image[30:90, 40:120] = 220
    return image


def test_auto_uses_opencv_quietly_when_rembg_is_off():
    result = segment(_image(), None, None, SegmentConfig(backend="auto", enable_rembg=False))
    assert result.backend == "opencv"
    assert not any("turned off" in warning for warning in result.warnings)


def test_auto_uses_rembg_when_enabled(monkeypatch):
    calls = []

    class FakeRembg:
        def segment(self, image_rgb, geometry_mask, *, refinement):
            calls.append(image_rgb.shape)
            return np.full(image_rgb.shape[:2], 255, np.uint8), []

    monkeypatch.setattr(segment_module, "RembgSegmenter", FakeRembg)
    result = segment(_image(), None, None, SegmentConfig(backend="auto", enable_rembg=True))
    assert result.backend == "rembg"
    assert calls
