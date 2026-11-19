import cv2
import numpy as np

from app.processing.detect import DetectConfig, detect_stickers
from app.processing.geometry import denormalize, mask_iou, polygon_mask
from app.tests.fixtures import (
    circle_scene,
    collection_scene,
    gradient_collection,
    low_contrast_scene,
    perspective_scene,
    rectangle_scene,
    star_scene,
)


def test_rectangular_sticker_is_detected_with_a_usable_overlap():
    image, truth = rectangle_scene()
    result = detect_stickers(image, DetectConfig(mode="single"))
    assert result.candidates
    best = result.candidates[0]
    guessed = polygon_mask(best.polygon, image.shape[1], image.shape[0])
    assert mask_iou(guessed, truth) > 0.8
    assert best.shape == "rect"
    assert best.perspective_suggested is True
    assert best.quad is not None and len(best.quad) == 4
    assert best.confidence > 0.45


def test_circular_sticker_is_not_forced_into_a_rectangle():
    image, truth = circle_scene()
    result = detect_stickers(image, DetectConfig(mode="single"))
    best = result.candidates[0]
    guessed = polygon_mask(best.polygon, image.shape[1], image.shape[0])
    assert mask_iou(guessed, truth) > 0.8
    assert best.shape == "circle"
    assert best.perspective_suggested is False


def test_irregular_silhouette_keeps_its_shape():
    image, truth = star_scene()
    result = detect_stickers(image, DetectConfig(mode="single"))
    best = result.candidates[0]
    guessed = polygon_mask(best.polygon, image.shape[1], image.shape[0])
    assert mask_iou(guessed, truth) > 0.75
    assert best.shape == "irregular"
    assert best.perspective_suggested is False


def test_collection_finds_each_separated_sticker():
    image, masks = collection_scene()
    result = detect_stickers(image, DetectConfig(mode="collection", min_area_ratio=0.01))
    assert len(result.candidates) >= 3
    claimed = set()
    for truth in masks:
        ious = []
        for index, candidate in enumerate(result.candidates):
            guessed = polygon_mask(candidate.polygon, image.shape[1], image.shape[0])
            ious.append((mask_iou(guessed, truth), index))
        score, index = max(ious)
        assert score > 0.7
        claimed.add(index)
    assert len(claimed) >= 3


def test_perspective_rectangle_corners_are_close_to_the_true_quad():
    image, _artwork, quad = perspective_scene()
    result = detect_stickers(image, DetectConfig(mode="single"))
    best = result.candidates[0]
    assert best.quad is not None
    guessed = denormalize(best.quad, image.shape[1], image.shape[0])
    for corner in quad:
        distance = np.linalg.norm(guessed - corner, axis=1).min()
        assert distance < 18


def test_low_contrast_fails_open_for_manual_selection():
    image = low_contrast_scene()
    result = detect_stickers(image, DetectConfig(mode="single"))
    assert result.candidates
    assert result.manual_recommended is True
    assert result.warnings


def test_lighting_gradient_does_not_swallow_two_stickers():
    image = gradient_collection()
    result = detect_stickers(image, DetectConfig(mode="collection", min_area_ratio=0.005))
    assert len(result.candidates) >= 2
    areas = sorted(candidate.area_ratio for candidate in result.candidates)
    assert areas[-1] < 0.5


def test_detection_is_deterministic():
    image, _truth = rectangle_scene()
    first = detect_stickers(image)
    second = detect_stickers(image)
    assert first.candidates[0].polygon == second.candidates[0].polygon
    assert first.candidates[0].confidence == second.candidates[0].confidence


def test_rounded_corner_stays_inside_the_outline():
    """A rounded sticker must not be cut across the corner.

    Simplifying by a fraction of the perimeter turns each round corner into
    a straight chord. The point on the arc has to stay inside the outline.
    """
    height, width = 560, 900
    image = np.zeros((height, width, 3), np.uint8)
    image[:, :] = (30, 32, 36)
    truth = np.zeros((height, width), np.uint8)
    x0, y0, x1, y1 = 70, 40, 830, 520
    radius = 90
    color = (214, 210, 202)
    for target in (image, truth):
        cv2.rectangle(target, (x0 + radius, y0), (x1 - radius, y1), color if target is image else 255, thickness=-1)
        cv2.rectangle(target, (x0, y0 + radius), (x1, y1 - radius), color if target is image else 255, thickness=-1)
        for cx, cy in (
            (x0 + radius, y0 + radius),
            (x1 - radius, y0 + radius),
            (x0 + radius, y1 - radius),
            (x1 - radius, y1 - radius),
        ):
            cv2.circle(target, (cx, cy), radius, color if target is image else 255, thickness=-1)

    result = detect_stickers(image, DetectConfig(mode="single"))
    guessed = polygon_mask(result.candidates[0].polygon, width, height)
    assert mask_iou(guessed, truth) > 0.9
    inset = radius - 4
    for cx, cy, degrees in (
        (x0 + radius, y0 + radius, 225),
        (x1 - radius, y0 + radius, 315),
        (x0 + radius, y1 - radius, 135),
        (x1 - radius, y1 - radius, 45),
    ):
        angle = np.deg2rad(degrees)
        px = int(round(cx + inset * np.cos(angle)))
        py = int(round(cy + inset * np.sin(angle)))
        assert truth[py, px] > 0
        assert guessed[py, px] > 0


def test_light_sticker_cropped_into_the_frame_keeps_its_silhouette():
    """A light sticker on a dark surface, with dark print, filling the frame.

    The sticker runs into the border band the detector samples as the surface,
    and it touches the top and bottom of the photo. The outline has to be the
    sticker, not a scrap of the printed edge.
    """
    height, width = 400, 1000
    image = np.zeros((height, width, 3), np.uint8)
    image[:, :] = (32, 34, 38)
    truth = np.zeros((height, width), np.uint8)
    # Right-hand sticker. Most of the border stays the dark surface, but the
    # sticker still occupies the top, bottom, and right edges.
    cv2.rectangle(image, (550, 0), (width - 1, height - 1), (214, 210, 202), thickness=-1)
    cv2.rectangle(truth, (550, 0), (width - 1, height - 1), 255, thickness=-1)
    cv2.rectangle(image, (640, 140), (860, 260), (30, 32, 36), thickness=-1)
    cv2.circle(image, (760, 80), 22, (28, 30, 34), thickness=-1)

    result = detect_stickers(image, DetectConfig(mode="single"))
    best = result.candidates[0]
    guessed = polygon_mask(best.polygon, width, height)
    assert best.area_ratio > 0.3
    assert mask_iou(guessed, truth) > 0.7


def test_specks_beside_one_sticker_are_not_called_overlapping():
    image = np.zeros((400, 700, 3), np.uint8)
    image[:, :] = (32, 34, 38)
    cv2.rectangle(image, (180, 60), (560, 340), (214, 210, 202), thickness=-1)
    cv2.circle(image, (40, 40), 16, (230, 228, 220), thickness=-1)
    cv2.circle(image, (70, 360), 14, (226, 224, 216), thickness=-1)
    result = detect_stickers(image, DetectConfig(mode="single"))
    assert result.candidates[0].area_ratio > 0.2
    assert not any("overlapping" in warning for warning in result.warnings)


def test_touching_rectangles_do_not_crash():
    image = rgb = np.zeros((400, 700, 3), np.uint8)
    image[:, :] = (170, 170, 174)
    cv2.rectangle(image, (40, 80), (330, 300), (200, 30, 30), thickness=-1)
    cv2.rectangle(image, (300, 90), (640, 310), (30, 80, 180), thickness=-1)
    result = detect_stickers(image, DetectConfig(mode="collection"))
    assert result.candidates
    assert isinstance(result.warnings, list)
    del rgb
