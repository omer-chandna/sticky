import cv2
import numpy as np

from app.processing.cutline import CutlineConfig, generate_cutline


def test_circle_cutline_is_closed_and_near_the_right_area():
    mask = np.zeros((240, 240), np.uint8)
    cv2.circle(mask, (120, 120), 80, 255, thickness=-1)
    result = generate_cutline(mask, CutlineConfig(simplify=0, smooth=0, offset_px=0, include_holes=True))
    assert result.closed
    assert result.path_d.strip().endswith("Z")
    assert result.point_count >= 8
    area = cv2.contourArea(result.contours[0])
    expected = np.pi * 80 * 80
    assert abs(area - expected) / expected < 0.12


def test_offset_grows_the_outline_and_holes_can_be_kept():
    mask = np.zeros((220, 220), np.uint8)
    cv2.circle(mask, (110, 110), 80, 255, thickness=-1)
    cv2.circle(mask, (110, 110), 28, 0, thickness=-1)
    base = generate_cutline(mask, CutlineConfig(simplify=0.1, smooth=0, include_holes=True))
    grown = generate_cutline(mask, CutlineConfig(simplify=0.1, smooth=0, offset_px=6, include_holes=True))
    assert base.holes >= 1
    assert grown.closed
    base_box = cv2.boundingRect(base.contours[0])
    grown_box = cv2.boundingRect(grown.contours[0])
    assert grown_box[2] > base_box[2]
