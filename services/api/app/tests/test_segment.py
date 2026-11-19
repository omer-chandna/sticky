import cv2
import numpy as np

from app.processing.geometry import normalize_points
from app.processing.pipeline import GeometryInput, PipelineConfig, StickerPipeline
from app.processing.segment import SegmentConfig, segment_image
from app.tests.fixtures import donut_scene, rectangle_scene, white_artwork_scene


def _polygon_from_mask(mask: np.ndarray, pad: int = 12) -> list[tuple[float, float]]:
    ys, xs = np.where(mask > 0)
    x0, x1 = max(0, xs.min() - pad), min(mask.shape[1] - 1, xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(mask.shape[0] - 1, ys.max() + pad)
    points = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32)
    return normalize_points(points, mask.shape[1], mask.shape[0])


def test_white_artwork_stays_opaque_on_a_dark_surface():
    image, truth = white_artwork_scene()
    polygon = _polygon_from_mask(truth, pad=8)
    result = StickerPipeline().run(
        image,
        PipelineConfig(
            geometry=GeometryInput(polygon=polygon, apply_perspective=False),
            segment=SegmentConfig(refinement=35, feather=0),
            max_dimension=800,
        ),
    )
    alpha = result.alpha
    # Map a point that was white artwork (inside the rectangle, away from the red circle).
    # The pipeline crops, so measure coverage instead of source coordinates.
    assert alpha.mean() > 40
    opaque = alpha > 200
    assert opaque.mean() > 0.5
    # Corners of the crop are the dark surface outside the loose polygon padding
    # or the sticker edge. The white region should dominate and stay solid.
    assert np.percentile(alpha, 80) > 240
    outside_like = alpha < 15
    # Padding around the selection should remain transparent.
    assert outside_like.mean() > 0.01


def test_die_cut_hole_matching_the_surface_stays_transparent():
    image, truth = donut_scene()
    polygon = _polygon_from_mask(truth, pad=18)
    alpha = segment_image(
        image,
        None,
        None,
        SegmentConfig(refinement=40, feather=0),
    ).alpha
    # Run through the crop path as a user would, with the polygon.
    cropped = StickerPipeline().run(
        image,
        PipelineConfig(
            geometry=GeometryInput(polygon=polygon),
            segment=SegmentConfig(refinement=40, feather=0),
            max_dimension=800,
        ),
    )
    center = cropped.alpha[cropped.alpha.shape[0] // 2, cropped.alpha.shape[1] // 2]
    assert center < 40
    assert cropped.alpha.max() == 255
    # The uncropped mask also keeps the hole.
    assert alpha[260, 260] < 40
    assert alpha[260, 120] > 200


def test_a_full_frame_quad_keeps_the_sticker_color():
    image, _truth = rectangle_scene()
    height, width = image.shape[:2]
    corners = normalize_points(np.array([[180, 130], [619, 130], [619, 469], [180, 469]], np.float32), width, height)
    result = StickerPipeline().run(
        image,
        PipelineConfig(
            geometry=GeometryInput(polygon=corners, quad=corners, apply_perspective=True),
            segment=SegmentConfig(refinement=40, feather=0),
            max_dimension=900,
        ),
    )
    alpha = result.image[:, :, 3]
    opaque = alpha > 200
    assert opaque.mean() > 0.75
    assert result.image[:, :, 0][opaque].mean() > 150


def test_textured_dark_print_stays_while_a_flat_hole_opens():
    """Ink can be as dark as the desk. An edge keeps it; a flat hole does not.

    An uneven desk stretches the color match until the print is deleted.
    A die-cut hole is a flat patch of that same desk, so it still opens.
    """
    height, width = 420, 640
    base = np.array([40, 42, 46], np.int16)
    noise = np.random.default_rng(0).integers(-14, 15, size=(height, width, 3), dtype=np.int16)
    image = np.clip(base + noise, 0, 255).astype(np.uint8)
    cv2.rectangle(image, (70, 40), (580, 370), (214, 210, 202), thickness=-1)
    dark = tuple(int(value) for value in np.clip(base - 6, 0, 255))
    light = tuple(int(value) for value in np.clip(base + 4, 0, 255))
    for y in range(155, 255):
        image[y, 150:340] = dark if (y // 2) % 2 == 0 else light
    cv2.circle(image, (480, 250), 30, tuple(int(value) for value in base), thickness=-1)
    geometry = np.zeros((height, width), np.uint8)
    cv2.rectangle(geometry, (50, 25), (600, 390), 255, thickness=-1)

    alpha = segment_image(image, geometry, None, SegmentConfig(refinement=40, feather=0)).alpha
    assert alpha[160, 200] > 200
    assert alpha[157, 200] > 200
    assert alpha[250, 480] < 40
    assert alpha[90, 100] > 200


def test_dark_print_stays_when_the_surface_sample_is_uneven():
    """Dark ink is not a die-cut hole just because the desk sample is uneven.

    A few bright pixels outside the selection used to stretch the surface
    match until the print was deleted. A hole that really is the desk color
    still stays open.
    """
    height, width = 360, 520
    image = np.zeros((height, width, 3), np.uint8)
    surface = (36, 38, 42)
    image[:, :] = surface
    image[0:30, 200:400] = (110, 112, 108)
    image[330:359, 80:240] = (110, 112, 108)
    image[40:300, 0:25] = (110, 112, 108)
    cv2.rectangle(image, (80, 50), (460, 310), (214, 208, 200), thickness=-1)
    cv2.rectangle(image, (150, 140), (300, 220), (58, 52, 48), thickness=-1)
    cv2.circle(image, (380, 230), 24, surface, thickness=-1)
    geometry = np.zeros((height, width), np.uint8)
    cv2.rectangle(geometry, (70, 40), (470, 320), 255, thickness=-1)

    alpha = segment_image(image, geometry, None, SegmentConfig(refinement=40, feather=0)).alpha
    assert alpha[180, 220] > 200
    assert alpha[230, 380] < 40
    assert alpha[90, 140] > 200


def test_manual_polygon_works_when_detection_would_be_unsure():
    image = np.zeros((240, 320, 3), np.uint8)
    image[:, :] = (140, 140, 140)
    image[60:180, 70:240] = (150, 148, 146)
    polygon = [(0.18, 0.2), (0.78, 0.2), (0.78, 0.78), (0.18, 0.78)]
    result = StickerPipeline().run(
        image,
        PipelineConfig(geometry=GeometryInput(polygon=polygon), max_dimension=400),
    )
    assert result.image.shape[2] == 4
    assert result.image[:, :, 3].max() > 0
