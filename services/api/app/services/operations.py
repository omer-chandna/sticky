"""Operations shared by synchronous routes and background jobs."""

from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Callable

import numpy as np
from PIL import Image

from app.core.config import Settings
from app.core.images import encode_png
from app.core.storage import Storage
from app.exports.pdf_export import build_sheet_pdf
from app.exports.render import Appearance, RenderedSticker, cutline_svg, hybrid_svg, render_sticker, vector_svg_with_size
from app.exports.sheet import LayoutResult, PlacedItem, SheetItem, SheetSpec, pack_sheet, validate_placement
from app.exports.zip_export import build_zip
from app.processing.cutline import CutlineConfig, generate_cutline
from app.processing.detect import DetectConfig, detect_stickers
from app.processing.pipeline import (
    GeometryInput,
    PipelineConfig,
    StickerPipeline,
    prepare_geometry,
)
from app.processing.restore import RestoreConfig
from app.processing.segment import SegmentConfig
from app.schemas.models import (
    AppearanceModel,
    CutlineRequest,
    DetectRequest,
    PngExportRequest,
    RestoreRequest,
    SheetRequest,
    SvgExportRequest,
    VectorRequest,
    ZipExportRequest,
)
from app.vectorization.vtracer_backend import VectorConfig, vectorize_image

Progress = Callable[[str], None]


def _noop(_stage: str) -> None:
    return None


def detect_upload(storage: Storage, request: DetectRequest) -> dict[str, Any]:
    image = _load_upload(storage, request.upload_id)
    result = detect_stickers(
        image,
        DetectConfig(
            mode=request.mode,
            min_area_ratio=request.min_area_ratio,
            max_candidates=request.max_candidates,
        ),
    )
    return {
        "upload_id": request.upload_id,
        "width": result.width,
        "height": result.height,
        "manual_recommended": result.manual_recommended,
        "warnings": result.warnings,
        "candidates": [
            {
                "id": candidate.id,
                "polygon": [{"x": x, "y": y} for x, y in candidate.polygon],
                "bbox": {
                    "x": candidate.bbox[0],
                    "y": candidate.bbox[1],
                    "width": candidate.bbox[2],
                    "height": candidate.bbox[3],
                },
                "quad": [{"x": x, "y": y} for x, y in candidate.quad] if candidate.quad else None,
                "confidence": candidate.confidence,
                "shape": candidate.shape,
                "area_ratio": candidate.area_ratio,
                "perspective_suggested": candidate.perspective_suggested,
            }
            for candidate in result.candidates
        ],
    }


def restore_upload(
    storage: Storage,
    settings: Settings,
    request: RestoreRequest,
    progress: Progress = _noop,
) -> dict[str, Any]:
    preview_limit, final_limit = settings.preview_max_dimension, settings.final_max_dimension
    key = _hash("restore", request.model_dump())
    cached = storage.cache_get(request.upload_id, key)
    if cached:
        progress("cleaning image")
        return cached

    progress("loading")
    pipeline = StickerPipeline()
    if request.prepared_artifact_id:
        prepared = _load_artifact_rgb(storage, request.prepared_artifact_id)
        progress("correcting perspective")
        brush = None
        geometry_mask = None
        if request.geometry.mask_png_base64:
            from app.processing.geometry import decode_mask

            brush = decode_mask(request.geometry.mask_png_base64, prepared.shape[1], prepared.shape[0])
        if request.geometry.polygon and not request.geometry.authoritative_mask:
            from app.processing.geometry import polygon_mask

            geometry_mask = polygon_mask(
                [(point.x, point.y) for point in request.geometry.polygon],
                prepared.shape[1],
                prepared.shape[0],
            )
        progress("removing background")
        segmented = pipeline.segment(
            prepared,
            geometry_mask,
            brush,
            SegmentConfig(
                refinement=request.segment.refinement,
                feather=0,
                backend=request.segment.backend,
                enable_rembg=settings.enable_rembg,
                authoritative_mask=request.geometry.authoritative_mask,
            ),
        )
        progress("cleaning image")
        restored = pipeline.restore(prepared, segmented.alpha, _restore_config(request))
        image = restored.image
        before = np.dstack([prepared[:, :, :3], segmented.alpha])
        warnings = [*segmented.warnings, *restored.warnings]
        transform = {"type": "prepared"}
        backend = segmented.backend
        prepared_rgb = prepared
    else:
        source = _load_upload(storage, request.upload_id)
        limit = preview_limit if request.quality == "preview" else final_limit
        progress("correcting perspective")
        working, _scale = _limit(source, limit)
        prepared_rgb, geometry_mask, brush, transform, prep_warnings = prepare_geometry(
            working, _geometry(request)
        )
        progress("removing background")
        segmented = pipeline.segment(
            prepared_rgb,
            geometry_mask,
            brush,
            SegmentConfig(
                refinement=request.segment.refinement,
                feather=0,
                backend=request.segment.backend,
                enable_rembg=settings.enable_rembg,
                authoritative_mask=request.geometry.authoritative_mask,
            ),
        )
        progress("cleaning image")
        restored = pipeline.restore(prepared_rgb, segmented.alpha, _restore_config(request))
        image = restored.image
        before = np.dstack([prepared_rgb[:, :, :3], segmented.alpha])
        warnings = [*prep_warnings, *segmented.warnings, *restored.warnings]
        backend = segmented.backend

    cutline = pipeline.generate_cutline(
        image[:, :, 3],
        CutlineConfig(simplify=0.22, smooth=min(0.45, request.restore.edge_smoothness / 140), include_holes=True),
    )
    prepared_record = storage.save_artifact(
        request.upload_id,
        kind="prepared",
        data=encode_png(prepared_rgb[:, :, :3]),
        meta={"role": "prepared"},
        suffix=".png",
    )
    restored_record = storage.save_artifact(
        request.upload_id,
        kind="rgba",
        data=encode_png(image),
        meta={
            "role": "restored",
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "warnings": _unique(warnings),
            "backend": backend,
            "quality": request.quality,
        },
        suffix=".png",
    )
    before_record = storage.save_artifact(
        request.upload_id,
        kind="rgba",
        data=encode_png(before),
        meta={"role": "before"},
        suffix=".png",
    )
    payload = {
        "upload_id": request.upload_id,
        "artifact_id": restored_record["artifact_id"],
        "prepared_artifact_id": prepared_record["artifact_id"],
        "before_artifact_id": before_record["artifact_id"],
        "preview_url": f"/api/artifacts/{restored_record['artifact_id']}",
        "before_url": f"/api/artifacts/{before_record['artifact_id']}",
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "warnings": _unique(warnings + cutline.warnings),
        "segment_backend": backend,
        "transform": {key: value for key, value in transform.items() if key != "matrix"},
        "cutline": {
            "path_d": cutline.path_d,
            "view_width": cutline.width,
            "view_height": cutline.height,
            "closed": cutline.closed,
            "point_count": cutline.point_count,
            "holes": cutline.holes,
        },
    }
    storage.cache_put(request.upload_id, key, payload)
    return payload


def vectorize_artifact(storage: Storage, request: VectorRequest, progress: Progress = _noop, max_dimension: int = 1200) -> dict[str, Any]:
    progress("vectorizing artwork")
    image, record = _load_artifact_rgba(storage, request.artifact_id)
    result = vectorize_image(
        image,
        VectorConfig(
            preset=request.preset,
            color_complexity=request.color_complexity,
            curve_smoothness=request.curve_smoothness,
            min_region=request.min_region,
            edge_detail=request.edge_detail,
            noise_filtering=request.noise_filtering,
            path_simplification=request.path_simplification,
            max_dimension=max_dimension,
        ),
    )
    saved = storage.save_artifact(
        record["upload_id"],
        kind="svg",
        data=result.svg.encode("utf-8"),
        meta={
            "role": "vector",
            "path_count": result.path_count,
            "fidelity": result.fidelity,
            "recommend_faithful": result.recommend_faithful,
            "width": result.width,
            "height": result.height,
            "preset": result.preset,
            "warnings": result.warnings,
        },
        suffix=".svg",
    )
    return {
        "artifact_id": saved["artifact_id"],
        "source_artifact_id": request.artifact_id,
        "svg": result.svg,
        "preview_url": f"/api/artifacts/{saved['artifact_id']}",
        "path_count": result.path_count,
        "width_px": result.width,
        "height_px": result.height,
        "fidelity": result.fidelity,
        "recommend_faithful": result.recommend_faithful,
        "byte_size": result.byte_size,
        "preset": result.preset,
        "warnings": result.warnings,
        "parameters": {key: value for key, value in result.parameters.items() if key != "preset"},
    }


def cutline_for_artifact(storage: Storage, request: CutlineRequest) -> dict[str, Any]:
    image, _record = _load_artifact_rgba(storage, request.artifact_id)
    alpha = image[:, :, 3]
    if request.border_enabled and request.border_mm > 0:
        import cv2

        border_px = max(1, int(round(request.border_mm / max(request.width_mm, 0.1) * alpha.shape[1])))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2 + 1, border_px * 2 + 1))
        alpha = cv2.dilate(alpha, kernel, iterations=1)
    offset_px = request.offset_mm / max(request.width_mm, 0.1) * alpha.shape[1]
    cutline = generate_cutline(
        alpha,
        CutlineConfig(
            offset_px=offset_px,
            simplify=request.simplify,
            smooth=request.smooth,
            include_holes=request.include_holes,
        ),
    )
    return {
        "path_d": cutline.path_d,
        "view_width": cutline.width,
        "view_height": cutline.height,
        "closed": cutline.closed,
        "point_count": cutline.point_count,
        "holes": cutline.holes,
        "warnings": cutline.warnings,
    }


def export_png(storage: Storage, request: PngExportRequest, progress: Progress = _noop) -> dict[str, Any]:
    progress("preparing export")
    image, record = _load_artifact_rgba(storage, request.artifact_id)
    rendered = render_sticker(image, _appearance(request.appearance))
    data = encode_png(rendered.image)
    saved = storage.save_artifact(
        record["upload_id"],
        kind="png",
        data=data,
        meta={**_render_meta(rendered, "faithful"), "filename": _filename(rendered, "png", "faithful")},
        suffix=".png",
    )
    filename = saved["filename"]
    return _export_payload(saved, filename, "image/png", rendered)


def export_svg(storage: Storage, request: SvgExportRequest, progress: Progress = _noop, max_dimension: int = 1200) -> dict[str, Any]:
    progress("preparing export")
    image, record = _load_artifact_rgba(storage, request.artifact_id)
    appearance = _appearance(request.appearance)
    rendered = render_sticker(image, appearance)
    if request.mode == "vector":
        progress("vectorizing artwork")
        traced = vectorize_image(rendered.image, _vector_config(request, max_dimension))
        svg = vector_svg_with_size(
            traced.svg,
            width_mm=rendered.occupied_width_mm,
            height_mm=rendered.occupied_height_mm,
            view_width=traced.width,
            view_height=traced.height,
        )
        warnings = _unique(rendered.warnings + traced.warnings)
        extra = {
            "path_count": traced.path_count,
            "fidelity": traced.fidelity,
            "recommend_faithful": traced.recommend_faithful,
            "mode": "vector",
        }
    else:
        svg = hybrid_svg(
            rendered.image,
            rendered.cutline,
            width_mm=rendered.occupied_width_mm,
            height_mm=rendered.occupied_height_mm,
        )
        warnings = rendered.warnings + [
            "This SVG embeds the raster artwork and a vector cutting outline. It is not a full vectorization."
        ]
        extra = {"path_count": 1 if rendered.cutline.path_d else 0, "fidelity": None, "recommend_faithful": False, "mode": "hybrid"}
    saved = storage.save_artifact(
        record["upload_id"],
        kind="svg",
        data=svg.encode("utf-8"),
        meta={
            **_render_meta(rendered, extra["mode"]),
            "warnings": warnings,
            **extra,
            "filename": _filename(rendered, "svg", extra["mode"]),
        },
        suffix=".svg",
    )
    filename = saved["filename"]
    payload = _export_payload(saved, filename, "image/svg+xml", rendered)
    payload["warnings"] = _unique(warnings)
    payload.update(extra)
    return payload


def export_cut_svg(storage: Storage, request: PngExportRequest, progress: Progress = _noop) -> dict[str, Any]:
    progress("preparing export")
    image, record = _load_artifact_rgba(storage, request.artifact_id)
    rendered = render_sticker(image, _appearance(request.appearance))
    svg = cutline_svg(
        rendered.cutline,
        width_mm=rendered.occupied_width_mm,
        height_mm=rendered.occupied_height_mm,
    )
    saved = storage.save_artifact(
        record["upload_id"],
        kind="svg",
        data=svg.encode("utf-8"),
        meta={**_render_meta(rendered, "cut"), "role": "cutline", "filename": _filename(rendered, "svg", "cut")},
        suffix=".svg",
    )
    filename = saved["filename"]
    return _export_payload(saved, filename, "image/svg+xml", rendered)


def export_zip(storage: Storage, request: ZipExportRequest, progress: Progress = _noop, max_dimension: int = 1200) -> dict[str, Any]:
    progress("preparing export")
    svg_request = SvgExportRequest(
        artifact_id=request.artifact_id,
        mode=request.mode,
        appearance=request.appearance,
        preset=request.preset,
    )
    png_info = export_png(storage, PngExportRequest(artifact_id=request.artifact_id, appearance=request.appearance), progress)
    svg_info = export_svg(storage, svg_request, progress, max_dimension=max_dimension)
    cut_info = export_cut_svg(storage, PngExportRequest(artifact_id=request.artifact_id, appearance=request.appearance), progress)
    png_bytes, _png_record = storage.artifact_bytes(png_info["artifact_id"])
    svg_bytes, _svg_record = storage.artifact_bytes(svg_info["artifact_id"])
    cut_bytes, _cut_record = storage.artifact_bytes(cut_info["artifact_id"])
    stem = _safe_stem(request.name)
    mode_label = "vector paths" if request.mode == "vector" else "hybrid SVG with embedded raster artwork and a vector cut outline"
    manifest = {
        "generator": "Sticky",
        "version": "0.1.0",
        "name": stem,
        "mode": request.mode,
        "width_mm": png_info["occupied_width_mm"],
        "height_mm": png_info["occupied_height_mm"],
        "artwork_width_mm": png_info["artwork_width_mm"],
        "artwork_height_mm": png_info["artwork_height_mm"],
        "files": [
            {
                "path": f"{stem}.png",
                "usage": "Transparent printable artwork, including any border you added. Use this for a printer or for Cricut Print Then Cut.",
                "width_mm": png_info["occupied_width_mm"],
                "height_mm": png_info["occupied_height_mm"],
            },
            {
                "path": f"{stem}.svg",
                "usage": mode_label,
                "width_mm": png_info["occupied_width_mm"],
                "height_mm": png_info["occupied_height_mm"],
            },
            {
                "path": f"{stem}.cut.svg",
                "usage": "Closed cutting silhouette only. Import this when you want a cut path, not the printed colors.",
                "width_mm": png_info["occupied_width_mm"],
                "height_mm": png_info["occupied_height_mm"],
            },
        ],
        "warnings": _unique(png_info.get("warnings", []) + svg_info.get("warnings", [])),
        "privacy": "This archive was created locally by Sticky. It was not sent to a third-party service.",
    }
    blob = build_zip(
        [(f"{stem}.png", png_bytes), (f"{stem}.svg", svg_bytes), (f"{stem}.cut.svg", cut_bytes)],
        manifest,
    )
    source, _record = storage.artifact_bytes(request.artifact_id)
    del source
    record = storage.get_artifact(request.artifact_id)
    saved = storage.save_artifact(
        record["upload_id"],
        kind="zip",
        data=blob,
        meta={"role": "bundle", "mode": request.mode, "filename": f"{stem}.zip"},
        suffix=".zip",
    )
    return {
        "artifact_id": saved["artifact_id"],
        "download_url": f"/api/artifacts/{saved['artifact_id']}?download=1",
        "filename": f"{stem}.zip",
        "media_type": "application/zip",
        "warnings": manifest["warnings"],
        "occupied_width_mm": png_info["occupied_width_mm"],
        "occupied_height_mm": png_info["occupied_height_mm"],
    }


def layout_sheet(request: SheetRequest) -> dict[str, Any]:
    spec = _sheet_spec(request)
    items = []
    for item in request.items:
        box_w, box_h = _sheet_footprint(item.appearance, item.rotation_deg)
        items.append(
            SheetItem(
                id=item.id,
                width_mm=box_w,
                height_mm=box_h,
                x_mm=item.x_mm,
                y_mm=item.y_mm,
                rotation_deg=item.rotation_deg,
            )
        )
    if request.auto_pack:
        layout = pack_sheet(spec, items)
    else:
        from app.exports.sheet import page_size_mm

        page_w, page_h = page_size_mm(spec)
        placed = [
            PlacedItem(
                id=item.id,
                x_mm=item.x_mm,
                y_mm=item.y_mm,
                width_mm=_sheet_footprint(item.appearance, item.rotation_deg)[0],
                height_mm=_sheet_footprint(item.appearance, item.rotation_deg)[1],
                rotation_deg=item.rotation_deg,
            )
            for item in request.items
        ]
        errors = validate_placement(spec, placed, allow_overlap=request.allow_overlap)
        if errors:
            raise ValueError(" ".join(errors))
        layout = LayoutResult(page_w, page_h, placed, [], [])
    return _layout_payload(layout)


def export_sheet(storage: Storage, request: SheetRequest, progress: Progress = _noop) -> dict[str, Any]:
    progress("preparing export")
    spec = _sheet_spec(request)
    rendered: dict[str, RenderedSticker] = {}
    images = {}
    for item in request.items:
        artwork, _record = _load_artifact_rgba(storage, item.artifact_id)
        appearance = _appearance(item.appearance)
        sticker = render_sticker(artwork, appearance)
        rendered[item.id] = sticker
        images[item.id] = Image.fromarray(sticker.image, mode="RGBA")
    boxes = []
    for item in request.items:
        occupied_w = rendered[item.id].occupied_width_mm
        occupied_h = rendered[item.id].occupied_height_mm
        box_w, box_h = _rotate_box(occupied_w, occupied_h, item.rotation_deg)
        boxes.append(
            SheetItem(
                id=item.id,
                width_mm=box_w,
                height_mm=box_h,
                x_mm=item.x_mm,
                y_mm=item.y_mm,
                rotation_deg=item.rotation_deg,
            )
        )
    if request.auto_pack:
        layout = pack_sheet(spec, boxes)
    else:
        from app.exports.sheet import page_size_mm

        page_w, page_h = page_size_mm(spec)
        placed = [
            PlacedItem(id=item.id, x_mm=item.x_mm, y_mm=item.y_mm, width_mm=item.width_mm, height_mm=item.height_mm, rotation_deg=item.rotation_deg)
            for item in boxes
        ]
        errors = validate_placement(spec, placed, allow_overlap=request.allow_overlap)
        if errors:
            raise ValueError(" ".join(errors))
        layout = LayoutResult(page_w, page_h, placed, [], [])
    if request.show_guides:
        layout.warnings.append("Cutting guides are drawn around each sticker and are not part of the artwork.")
    pdf_bytes = build_sheet_pdf(spec, layout, images, show_guides=request.show_guides)
    upload_id = storage.get_artifact(request.items[0].artifact_id)["upload_id"]
    saved = storage.save_artifact(
        upload_id,
        kind="pdf",
        data=pdf_bytes,
        meta={
            "role": "sheet",
            "page_width_mm": layout.page_width_mm,
            "page_height_mm": layout.page_height_mm,
            "warnings": layout.warnings,
            "filename": f"sticky-sheet-{spec.page}.pdf",
        },
        suffix=".pdf",
    )
    payload = _layout_payload(layout)
    payload.update(
        {
            "artifact_id": saved["artifact_id"],
            "download_url": f"/api/artifacts/{saved['artifact_id']}?download=1",
            "filename": f"sticky-sheet-{spec.page}.pdf",
            "media_type": "application/pdf",
        }
    )
    return payload


def _layout_payload(layout: LayoutResult) -> dict[str, Any]:
    return {
        "page_width_mm": layout.page_width_mm,
        "page_height_mm": layout.page_height_mm,
        "items": [
            {
                "id": item.id,
                "x_mm": item.x_mm,
                "y_mm": item.y_mm,
                "width_mm": item.width_mm,
                "height_mm": item.height_mm,
                "rotation_deg": item.rotation_deg,
            }
            for item in layout.items
        ],
        "overflows": layout.overflows,
        "warnings": layout.warnings,
    }


def _geometry(request: RestoreRequest) -> GeometryInput:
    geometry = request.geometry
    return GeometryInput(
        polygon=[(point.x, point.y) for point in geometry.polygon] if geometry.polygon else None,
        quad=[(point.x, point.y) for point in geometry.quad] if geometry.quad else None,
        apply_perspective=geometry.apply_perspective,
        mask_png_base64=geometry.mask_png_base64,
        authoritative_mask=geometry.authoritative_mask,
    )


def _restore_config(request: RestoreRequest) -> RestoreConfig:
    restore = request.restore
    return RestoreConfig(
        cleanup_strength=restore.cleanup_strength,
        edge_smoothness=restore.edge_smoothness,
        color_correction=restore.color_correction,
        sharpness=restore.sharpness,
        brightness=restore.brightness,
        contrast=restore.contrast,
        saturation=restore.saturation,
        exposure=restore.exposure,
        denoise=restore.denoise,
        white_balance=restore.white_balance,
        clahe=restore.clahe,
    )


def _appearance(model: AppearanceModel) -> Appearance:
    return Appearance(
        width_mm=model.width_mm,
        height_mm=model.height_mm,
        background=model.background,
        background_color=model.background_color,
        border_enabled=model.border_enabled,
        border_color=model.border_color,
        border_mm=model.border_mm,
        cut_offset_mm=model.cut_offset_mm,
        cut_simplify=model.cut_simplify,
        cut_smooth=model.cut_smooth,
        include_holes=model.include_holes,
        rotation_deg=model.rotation_deg,
        flip_h=model.flip_h,
        flip_v=model.flip_v,
        dpi=model.dpi,
        show_cut_guides=model.show_cut_guides,
    )


def _vector_config(request: SvgExportRequest, max_dimension: int) -> VectorConfig:
    return VectorConfig(
        preset=request.preset,
        color_complexity=request.color_complexity,
        curve_smoothness=request.curve_smoothness,
        min_region=request.min_region,
        edge_detail=request.edge_detail,
        noise_filtering=request.noise_filtering,
        path_simplification=request.path_simplification,
        max_dimension=max_dimension,
    )


def _sheet_spec(request: SheetRequest) -> SheetSpec:
    return SheetSpec(
        page=request.page,
        orientation=request.orientation,
        custom_width_mm=request.custom_width_mm,
        custom_height_mm=request.custom_height_mm,
        margin_mm=request.margin_mm,
        spacing_mm=request.spacing_mm,
        calibration_square=request.calibration_square,
    )


def _occupied(appearance: AppearanceModel) -> tuple[float, float]:
    border = appearance.border_mm * 2 if appearance.border_enabled else 0
    return appearance.width_mm + border, appearance.height_mm + border


def _sheet_footprint(appearance: AppearanceModel, rotation: float) -> tuple[float, float]:
    width, height = _occupied(appearance)
    return _rotate_box(width, height, appearance.rotation_deg + rotation)


def _rotate_box(width: float, height: float, degrees: float) -> tuple[float, float]:
    radians = np.deg2rad(degrees)
    box_w = abs(width * np.cos(radians)) + abs(height * np.sin(radians))
    box_h = abs(width * np.sin(radians)) + abs(height * np.cos(radians))
    return box_w, box_h


def _render_meta(rendered: RenderedSticker, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "artwork_width_mm": rendered.artwork_width_mm,
        "artwork_height_mm": rendered.artwork_height_mm,
        "occupied_width_mm": rendered.occupied_width_mm,
        "occupied_height_mm": rendered.occupied_height_mm,
        "warnings": rendered.warnings,
        "width": int(rendered.image.shape[1]),
        "height": int(rendered.image.shape[0]),
    }


def _export_payload(saved: dict[str, Any], filename: str, media_type: str, rendered: RenderedSticker) -> dict[str, Any]:
    return {
        "artifact_id": saved["artifact_id"],
        "download_url": f"/api/artifacts/{saved['artifact_id']}?download=1",
        "preview_url": f"/api/artifacts/{saved['artifact_id']}",
        "filename": filename,
        "media_type": media_type,
        "artwork_width_mm": rendered.artwork_width_mm,
        "artwork_height_mm": rendered.artwork_height_mm,
        "occupied_width_mm": rendered.occupied_width_mm,
        "occupied_height_mm": rendered.occupied_height_mm,
        "warnings": rendered.warnings,
        "width_px": int(rendered.image.shape[1]),
        "height_px": int(rendered.image.shape[0]),
    }


def _filename(rendered: RenderedSticker, extension: str, mode: str) -> str:
    width = f"{rendered.occupied_width_mm:.0f}".replace(".", "")
    height = f"{rendered.occupied_height_mm:.0f}".replace(".", "")
    return f"sticky-{width}x{height}mm-{mode}.{extension}"


def _safe_stem(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in name.strip().lower())
    return cleaned[:48] or "sticker"


def _hash(kind: str, payload: dict[str, Any]) -> str:
    raw = json.dumps({"kind": kind, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_upload(storage: Storage, upload_id: str) -> np.ndarray:
    path = storage.upload_path(upload_id)
    with Image.open(path) as image:
        image.load()
        return np.array(image.convert("RGB"))


def _load_artifact_rgba(storage: Storage, artifact_id: str) -> tuple[np.ndarray, dict[str, Any]]:
    data, record = storage.artifact_bytes(artifact_id)
    if record.get("suffix") != ".png":
        raise ValueError("That file is not a sticker image.")
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        return np.array(image.convert("RGBA")), record


def _load_artifact_rgb(storage: Storage, artifact_id: str) -> np.ndarray:
    rgba, _record = _load_artifact_rgba(storage, artifact_id)
    return rgba[:, :, :3]


def _limit(image: np.ndarray, max_dimension: int) -> tuple[np.ndarray, float]:
    import cv2

    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_dimension:
        return image, 1.0
    scale = max_dimension / float(longest)
    resized = cv2.resize(
        image,
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def _unique(warnings: list[str]) -> list[str]:
    seen: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.append(warning)
    return seen
