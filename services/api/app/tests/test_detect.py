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


def test_touching_rectangles_do_not_crash():
    image = rgb = np.zeros((400, 700, 3), np.uint8)
    image[:, :] = (170, 170, 174)
    cv2.rectangle(image, (40, 80), (330, 300), (200, 30, 30), thickness=-1)
    cv2.rectangle(image, (300, 90), (640, 310), (30, 80, 180), thickness=-1)
    result = detect_stickers(image, DetectConfig(mode="collection"))
    assert result.candidates
    assert isinstance(result.warnings, list)
    del rgb
