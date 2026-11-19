import re

import cv2
import numpy as np

from app.vectorization.redraw import RedrawConfig, flatten_artwork
from app.vectorization.vtracer_backend import VectorConfig, vectorize_image


def _photo_of_sticker(seed: int = 0) -> np.ndarray:
    """A grey panel lit unevenly, a black outline and a dark mark, with camera grain."""
    h, w = 160, 240
    rgba = np.zeros((h, w, 4), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    panel = 150 + 30 * (xx / w)  # lighting ramp across one grey ink
    rgb = np.dstack([panel, panel, panel * 0.95])
    cv2.rectangle(rgb, (20, 20), (219, 139), (25, 25, 25), 8)  # black outline
    cv2.circle(rgb, (120, 80), 22, (70, 60, 55), -1)  # dark mark
    noise = np.random.default_rng(seed).normal(0, 6, rgb.shape)
    rgba[..., :3] = np.clip(rgb + noise, 0, 255).astype(np.uint8)
    rgba[12:148, 12:228, 3] = 255
    return rgba


def _inks_used(image: np.ndarray) -> int:
    opaque = image[..., 3] > 0
    return len(np.unique(image[opaque][:, :3], axis=0))


def test_lighting_ramp_becomes_one_ink_and_real_edges_survive():
    result = flatten_artwork(_photo_of_sticker())
    image = result.image
    assert image.shape[:2] == (320, 480)  # traced at 2x
    # The ramped panel is a single flat ink from left to right.
    left, right = image[100, 70, :3], image[100, 400, :3]
    assert np.array_equal(left, right)
    # The black outline and the dark mark stay distinct from the panel.
    outline, mark = image[40, 240, :3], image[160, 240, :3]
    assert int(outline.mean()) < 60
    assert not np.array_equal(mark, left)
    assert _inks_used(image) <= 4


def test_flatten_is_deterministic():
    a = flatten_artwork(_photo_of_sticker(1)).image
    b = flatten_artwork(_photo_of_sticker(1)).image
    assert np.array_equal(a, b)


def test_transparent_input_returns_empty_image():
    empty = np.zeros((40, 40, 4), np.uint8)
    result = flatten_artwork(empty, RedrawConfig())
    assert result.image.shape == (80, 80, 4)
    assert not result.image[..., 3].any()


def test_redraw_svg_opens_at_the_input_size():
    result = vectorize_image(_photo_of_sticker(), VectorConfig(preset="redraw"))
    header = re.search(r"<svg[^>]*>", result.svg).group(0)
    assert 'width="240"' in header and 'height="160"' in header
    assert 'viewBox="0 0 480 320"' in header
    assert result.preset == "redraw"
    assert result.path_count > 0
    assert result.fidelity > 0.85
