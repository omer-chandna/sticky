"""Combining several photos of one flat surface."""

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.processing.fuse import FuseConfig, fuse_photos
from app.tests.fixtures import png_bytes

VIEW = (900, 640)


def _scene() -> np.ndarray:
    """A lid with two stickers carrying fine text, plus surface texture for matching."""
    rng = np.random.default_rng(7)
    scene = np.full((800, 1200, 3), (40, 42, 46), np.uint8)
    scene += rng.integers(0, 8, scene.shape, dtype=np.uint8)
    for x, y, colour, text in [(120, 140, (230, 200, 60), "Sticky 0.1"), (640, 380, (60, 140, 220), "Fusion 123")]:
        cv2.rectangle(scene, (x, y), (x + 440, y + 260), (235, 232, 222), -1)
        cv2.rectangle(scene, (x + 14, y + 14), (x + 426, y + 246), colour, -1)
        cv2.putText(scene, text, (x + 40, y + 110), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (20, 20, 20), 3, cv2.LINE_AA)
        cv2.putText(scene, "the quick brown fox 0123456789", (x + 30, y + 190), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (25, 25, 25), 1, cv2.LINE_AA)
    return scene


def _view(scene: np.ndarray, seed: int, glare: bool = True, offset=(0.0, 0.0)) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    vw, vh = VIEW
    h, w = scene.shape[:2]
    cx, cy = w / 2 + offset[0] + rng.uniform(-60, 60), h / 2 + offset[1] + rng.uniform(-40, 40)
    angle = np.deg2rad(rng.uniform(-3, 3))
    corners = np.float32([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * [vw / 2, vh / 2]
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    src = (corners @ rotation.T + [cx, cy] + rng.uniform(-12, 12, (4, 2))).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(src, np.float32([[0, 0], [vw, 0], [vw, vh], [0, vh]]))
    image = cv2.warpPerspective(scene, matrix, (vw, vh), flags=cv2.INTER_AREA).astype(np.float32)
    image *= rng.uniform(0.93, 1.07)
    image += rng.normal(0, 9, image.shape)
    if glare:
        yy, xx = np.mgrid[0:vh, 0:vw]
        gx, gy = rng.uniform(150, vw - 150), rng.uniform(150, vh - 150)
        image += (np.exp(-(((xx - gx) / 80) ** 2 + ((yy - gy) / 55) ** 2)) * 260)[..., None]
    return np.clip(image, 0, 255).astype(np.uint8), matrix


def _error_against_truth(image: np.ndarray, truth: np.ndarray) -> float:
    sift = cv2.SIFT_create(4000)
    ka, da = sift.detectAndCompute(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), None)
    kb, db = sift.detectAndCompute(cv2.cvtColor(truth, cv2.COLOR_RGB2GRAY), None)
    good = [m for m, n in cv2.BFMatcher().knnMatch(da, db, k=2) if m.distance < 0.7 * n.distance]
    src = np.float32([ka[m.queryIdx].pt for m in good])
    dst = np.float32([kb[m.trainIdx].pt for m in good])
    matrix, _ = cv2.findHomography(src, dst, cv2.RANSAC, 2.0)
    aligned = cv2.warpPerspective(image, matrix, (truth.shape[1], truth.shape[0]), flags=cv2.INTER_CUBIC)
    inner = (slice(80, -80), slice(80, -80))
    return float(np.abs(aligned.astype(np.float32) - truth.astype(np.float32))[inner].mean())


def test_combining_removes_grain_and_glare():
    scene = _scene()
    views = [_view(scene, seed) for seed in range(4)]
    result = fuse_photos([image for image, _m in views], FuseConfig(tile=512))
    assert result.used == [0, 1, 2, 3]
    assert not result.dropped
    reference_image, reference_matrix = views[result.reference]
    truth = cv2.warpPerspective(scene, reference_matrix, VIEW, flags=cv2.INTER_AREA)
    single = _error_against_truth(reference_image, truth)
    combined = _error_against_truth(result.image, truth)
    assert combined < 0.6 * single, (combined, single)


def test_a_photo_that_does_not_overlap_is_left_out_with_a_warning():
    scene = _scene()
    photos = [_view(scene, seed, glare=False)[0] for seed in range(3)]
    unrelated = np.random.default_rng(99).integers(0, 255, (VIEW[1], VIEW[0], 3), dtype=np.uint8)
    unrelated = cv2.GaussianBlur(unrelated, (0, 0), 6)
    result = fuse_photos([*photos, unrelated], FuseConfig(tile=512))
    assert result.dropped == [3]
    assert any("did not overlap" in warning for warning in result.warnings)


def test_photos_that_never_line_up_raise_a_clear_error():
    rng = np.random.default_rng(1)
    noise = [cv2.GaussianBlur(rng.integers(0, 255, (400, 600, 3), dtype=np.uint8), (0, 0), 8) for _ in range(2)]
    with pytest.raises(ValueError, match="could not be lined up"):
        fuse_photos(noise)
    with pytest.raises(ValueError, match="at least two"):
        fuse_photos(noise[:1])


def test_fuse_job_creates_a_new_upload(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path / "data", job_workers=1)))
    scene = _scene()
    ids = []
    for seed in range(3):
        image, _matrix = _view(scene, seed)
        response = client.post("/api/uploads", files={"file": (f"lid-{seed}.png", png_bytes(image), "image/png")})
        assert response.status_code == 200, response.text
        ids.append(response.json()["upload_id"])
    job = client.post("/api/jobs", json={"kind": "fuse", "fuse": {"upload_ids": ids}}).json()
    deadline = time.time() + 120
    while True:
        status = client.get(f"/api/jobs/{job['job_id']}").json()
        if status["status"] in ("completed", "failed") or time.time() > deadline:
            break
        time.sleep(0.2)
    assert status["status"] == "completed", status
    result = status["result"]
    assert result["photos_used"] == 3
    assert result["source_format"] == "combined"
    assert result["filename"].endswith("-combined.png")
    assert client.get(f"/api/uploads/{result['upload_id']}").status_code == 200
    detected = client.post("/api/detect", json={"upload_id": result["upload_id"], "mode": "collection"})
    assert detected.status_code == 200
    assert len(detected.json()["candidates"]) >= 2


def test_fuse_needs_two_photos(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path / "data", job_workers=1)))
    response = client.post("/api/jobs", json={"kind": "fuse", "fuse": {"upload_ids": ["a" * 32]}})
    assert response.status_code == 422
