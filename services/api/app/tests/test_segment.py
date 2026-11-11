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
