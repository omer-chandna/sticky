"""HTTP tests for the photo → sticker → sheet path."""

import io
import time
import zipfile
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from app.core.config import Settings
from app.main import create_app
from app.tests.fixtures import collection_scene, jpeg_with_orientation, png_bytes, rectangle_scene
from app.vectorization.svgutil import count_paths, has_embedded_image, sanitize_svg


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        cors_origins="http://localhost:3000",
        artifact_ttl_hours=6,
        preview_max_dimension=900,
        final_max_dimension=1400,
        vector_max_dimension=600,
        job_workers=1,
    )
    return TestClient(create_app(settings))


def _upload(client: TestClient, image: np.ndarray, name: str = "sticker.png") -> dict:
    response = client.post("/api/uploads", files={"file": (name, png_bytes(image), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


def _restore(client: TestClient, upload_id: str, polygon: list[dict] | None = None) -> dict:
    body = {
        "upload_id": upload_id,
        "quality": "preview",
        "geometry": {"polygon": polygon, "apply_perspective": False},
        "segment": {"refinement": 30, "feather": 0, "backend": "opencv"},
        "restore": {
            "cleanup_strength": 0,
            "edge_smoothness": 0,
            "color_correction": 0,
            "sharpness": 0,
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "exposure": 0,
            "denoise": 0,
            "white_balance": 0,
            "clahe": False,
        },
    }
    response = client.post("/api/process/restore", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_has_no_telemetry(tmp_path: Path):
    client = _client(tmp_path)
    payload = client.get("/api/health").json()
    assert payload["name"] == "Sticky"
    assert payload["telemetry"] is False
    assert payload["third_party_image_services"] is False
    assert payload["rembg_enabled"] is False


def test_rejects_a_fake_jpeg_and_accepts_exif_orientation(tmp_path: Path):
    client = _client(tmp_path)
    bad = client.post("/api/uploads", files={"file": ("photo.jpg", b"not really a jpeg", "image/jpeg")})
    assert bad.status_code == 400
    assert "HEIC" in bad.json()["detail"] or "Unsupported" in bad.json()["detail"]

    wide = np.zeros((80, 220, 3), np.uint8)
    wide[:, :] = (180, 180, 180)
    wide[10:30, 5:25] = (220, 20, 20)
    oriented = client.post(
        "/api/uploads",
        files={"file": ("turned.jpg", jpeg_with_orientation(wide), "image/jpeg")},
    )
    assert oriented.status_code == 200, oriented.text
    body = oriented.json()
    # Orientation 6 swaps the stored 220×80 frame into a tall image.
    assert body["height"] > body["width"]


def test_single_sticker_export_png_and_real_svg(tmp_path: Path):
    client = _client(tmp_path)
    image, _mask = rectangle_scene()
    uploaded = _upload(client, image)
    detected = client.post("/api/detect", json={"upload_id": uploaded["upload_id"], "mode": "single"}).json()
    assert detected["candidates"]
    polygon = detected["candidates"][0]["polygon"]
    restored = _restore(client, uploaded["upload_id"], polygon)
    assert restored["width"] > 20
    assert restored["cutline"]["closed"] is True

    preview = client.get(restored["preview_url"])
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG")
    with Image.open(io.BytesIO(preview.content)) as artwork:
        assert artwork.mode == "RGBA"
        assert artwork.getextrema()[3][0] < 20

    appearance = {
        "width_mm": 80,
        "height_mm": 50,
        "background": "transparent",
        "border_enabled": True,
        "border_color": "#ffffff",
        "border_mm": 2,
        "dpi": 120,
    }
    png = client.post(
        "/api/exports/png",
        json={"artifact_id": restored["artifact_id"], "appearance": appearance},
    ).json()
    assert png["occupied_width_mm"] == 84
    assert abs(png["occupied_height_mm"] - 54) < 0.2
    png_bytes_out = client.get(png["download_url"]).content
    with Image.open(io.BytesIO(png_bytes_out)) as exported:
        assert exported.mode == "RGBA"
        assert exported.size[0] > exported.size[1]

    svg_response = client.post(
        "/api/exports/svg",
        json={"artifact_id": restored["artifact_id"], "mode": "vector", "appearance": appearance, "preset": "logo"},
    )
    assert svg_response.status_code == 200, svg_response.text
    svg_body = svg_response.json()
    svg = client.get(svg_body["download_url"]).content.decode("utf-8")
    sanitize_svg(svg, allow_embedded_png=False)
    assert count_paths(svg) >= 1
    assert not has_embedded_image(svg)
    assert "mm" in svg
    assert 'data-sticky-mode="vector"' in svg
    assert svg_body["fidelity"] is not None

    hybrid = client.post(
        "/api/exports/svg",
        json={"artifact_id": restored["artifact_id"], "mode": "hybrid", "appearance": appearance},
    ).json()
    hybrid_svg = client.get(hybrid["download_url"]).content.decode("utf-8")
    assert "embedded raster" in hybrid_svg.lower() or "Hybrid SVG" in hybrid_svg
    assert has_embedded_image(hybrid_svg)
    assert 'data-sticky-mode="hybrid"' in hybrid_svg

    bundle = client.post(
        "/api/exports/zip",
        json={"artifact_id": restored["artifact_id"], "mode": "vector", "appearance": appearance, "name": "Camp badge"},
    ).json()
    archive = zipfile.ZipFile(io.BytesIO(client.get(bundle["download_url"]).content))
    names = set(archive.namelist())
    assert "manifest.json" in names
    assert any(name.endswith(".png") for name in names)
    assert any(name.endswith(".cut.svg") for name in names)
    manifest = archive.read("manifest.json").decode("utf-8")
    assert "Print Then Cut" in manifest
    assert "width_mm" in manifest


def test_collection_sheet_pdf_is_exact_letter_and_does_not_overlap(tmp_path: Path):
    client = _client(tmp_path)
    image, _masks = collection_scene()
    uploaded = _upload(client, image, "laptop.png")
    detected = client.post(
        "/api/detect",
        json={"upload_id": uploaded["upload_id"], "mode": "collection", "min_area_ratio": 0.01},
    ).json()
    assert len(detected["candidates"]) >= 2
    artifact_ids = []
    for candidate in detected["candidates"][:2]:
        restored = _restore(client, uploaded["upload_id"], candidate["polygon"])
        artifact_ids.append(restored["artifact_id"])

    appearance = {"width_mm": 90, "height_mm": 60, "dpi": 72, "border_enabled": False}
    layout = client.post(
        "/api/exports/sheet/layout",
        json={
            "page": "letter",
            "orientation": "portrait",
            "margin_mm": 12,
            "spacing_mm": 4,
            "auto_pack": True,
            "items": [
                {"id": "one", "artifact_id": artifact_ids[0], "appearance": appearance},
                {"id": "two", "artifact_id": artifact_ids[1], "appearance": appearance},
            ],
        },
    ).json()
    assert layout["page_width_mm"] == 215.9
    assert layout["page_height_mm"] == 279.4
    assert len(layout["items"]) == 2
    a, b = layout["items"]
    separated = (
        a["x_mm"] + a["width_mm"] <= b["x_mm"] + 0.2
        or b["x_mm"] + b["width_mm"] <= a["x_mm"] + 0.2
        or a["y_mm"] + a["height_mm"] <= b["y_mm"] + 0.2
        or b["y_mm"] + b["height_mm"] <= a["y_mm"] + 0.2
    )
    assert separated

    pdf = client.post(
        "/api/exports/sheet",
        json={
            "page": "letter",
            "orientation": "portrait",
            "margin_mm": 14,
            "spacing_mm": 4,
            "auto_pack": True,
            "calibration_square": True,
            "items": [
                {"id": "one", "artifact_id": artifact_ids[0], "appearance": appearance},
                {"id": "two", "artifact_id": artifact_ids[1], "appearance": appearance},
            ],
        },
    )
    assert pdf.status_code == 200, pdf.text
    reader = PdfReader(io.BytesIO(client.get(pdf.json()["download_url"]).content))
    box = reader.pages[0].mediabox
    assert abs(float(box.width) - 612) < 1.5
    assert abs(float(box.height) - 792) < 1.5
    text = reader.pages[0].extract_text() or ""
    assert "Actual Size" in text or "100%" in text


def test_manual_overlap_is_rejected_and_jobs_record_real_stages(tmp_path: Path):
    client = _client(tmp_path)
    image, _mask = rectangle_scene()
    uploaded = _upload(client, image)
    restored = _restore(client, uploaded["upload_id"], [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}])
    appearance = {"width_mm": 40, "height_mm": 40, "dpi": 72}
    overlap = client.post(
        "/api/exports/sheet",
        json={
            "page": "a4",
            "auto_pack": False,
            "allow_overlap": False,
            "margin_mm": 10,
            "items": [
                {"id": "a", "artifact_id": restored["artifact_id"], "x_mm": 20, "y_mm": 20, "appearance": appearance},
                {"id": "b", "artifact_id": restored["artifact_id"], "x_mm": 30, "y_mm": 30, "appearance": appearance},
            ],
        },
    )
    assert overlap.status_code == 400
    assert "overlap" in overlap.json()["detail"].lower()

    job = client.post(
        "/api/jobs",
        json={
            "kind": "restore",
            "restore": {
                "upload_id": uploaded["upload_id"],
                "quality": "preview",
                "geometry": {
                    "polygon": [
                        {"x": 0.2, "y": 0.2},
                        {"x": 0.8, "y": 0.2},
                        {"x": 0.8, "y": 0.8},
                        {"x": 0.2, "y": 0.8},
                    ]
                },
                "restore": {"cleanup_strength": 0, "sharpness": 0, "color_correction": 0, "edge_smoothness": 0},
            },
        },
    ).json()
    status = {}
    for _ in range(50):
        status = client.get(f"/api/jobs/{job['job_id']}").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert status["status"] == "completed", status
    assert "removing background" in status["stages_completed"]
    assert "cleaning image" in status["stages_completed"]
    assert status["result"]["artifact_id"]


def test_delete_upload_removes_the_photo(tmp_path: Path):
    client = _client(tmp_path)
    image, _mask = rectangle_scene()
    uploaded = _upload(client, image)
    assert client.delete(f"/api/uploads/{uploaded['upload_id']}").status_code == 200
    missing = client.get(f"/api/uploads/{uploaded['upload_id']}")
    assert missing.status_code == 404
