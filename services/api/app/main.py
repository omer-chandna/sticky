"""FastAPI application.

The processing package does not import this module, so the same pipeline can
be reused outside the web server.
"""

from __future__ import annotations

import logging
import mimetypes
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app import __version__
from app.core.config import Settings
from app.core.images import ImageRejected, encode_preview, load_image_bytes
from app.core.storage import Storage, StorageError
from app.jobs.manager import JobManager
from app.schemas.models import (
    CutlineRequest,
    DetectRequest,
    JobCreateRequest,
    PngExportRequest,
    RestoreRequest,
    SheetRequest,
    SvgExportRequest,
    VectorRequest,
    ZipExportRequest,
)
from app.services import operations
from app.vectorization.svgutil import SvgError

logger = logging.getLogger("sticky")

MEDIA_TYPES = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    storage = Storage(settings)
    jobs = JobManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        storage.cleanup_expired()
        stop = threading.Event()

        def loop() -> None:
            while not stop.wait(600):
                storage.cleanup_expired()

        thread = threading.Thread(target=loop, name="sticky-cleanup", daemon=True)
        thread.start()
        yield
        stop.set()

    app = FastAPI(
        title="Sticky",
        version=__version__,
        summary="Photo-to-sticker reconstruction. No account and no third-party image APIs.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.storage = storage
    app.state.jobs = jobs

    @app.exception_handler(StorageError)
    async def missing(_request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ImageRejected)
    async def rejected(_request: Request, exc: ImageRejected) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(SvgError)
    async def bad_svg(_request: Request, exc: SvgError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def bad_value(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "name": "Sticky",
            "version": __version__,
            "segmentation_backend": settings.segmentation_backend,
            "rembg_enabled": settings.enable_rembg,
            "telemetry": False,
            "third_party_image_services": False,
            "artifact_ttl_hours": settings.artifact_ttl_hours,
        }

    @app.post("/api/uploads")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        data = await file.read()
        loaded = load_image_bytes(data, max_pixels=settings.max_pixels, max_bytes=settings.max_upload_bytes)
        meta = storage.create_upload(loaded, file.filename or "sticker")
        return {
            **meta,
            "preview_url": f"/api/uploads/{meta['upload_id']}/image?max_dimension={settings.preview_max_dimension}",
        }

    @app.get("/api/uploads/{upload_id}")
    def get_upload(upload_id: str) -> dict[str, Any]:
        meta = storage.get_upload(upload_id)
        meta["preview_url"] = f"/api/uploads/{upload_id}/image?max_dimension={settings.preview_max_dimension}"
        return meta

    @app.get("/api/uploads/{upload_id}/image")
    def upload_image(upload_id: str, max_dimension: int = 1600) -> Response:
        path = storage.upload_path(upload_id)
        if max_dimension <= 0:
            raise HTTPException(status_code=400, detail="Preview size must be positive.")
        max_dimension = min(max_dimension, settings.final_max_dimension)
        array = operations._load_upload(storage, upload_id)
        body = encode_preview(array, max_dimension)
        media = "image/png" if body.startswith(b"\x89PNG") else "image/jpeg"
        del path
        return Response(content=body, media_type=media, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})

    @app.delete("/api/uploads/{upload_id}")
    def delete_upload(upload_id: str) -> dict[str, bool]:
        storage.delete_upload(upload_id)
        return {"deleted": True}

    @app.post("/api/detect")
    def detect(request: DetectRequest) -> dict[str, Any]:
        return operations.detect_upload(storage, request)

    @app.post("/api/process/restore")
    def restore(request: RestoreRequest) -> dict[str, Any]:
        return operations.restore_upload(storage, settings, request)

    @app.post("/api/process/vectorize")
    def vectorize(request: VectorRequest) -> dict[str, Any]:
        return operations.vectorize_artifact(storage, request, max_dimension=settings.vector_max_dimension)

    @app.post("/api/process/cutline")
    def cutline(request: CutlineRequest) -> dict[str, Any]:
        return operations.cutline_for_artifact(storage, request)

    @app.post("/api/exports/png")
    def export_png(request: PngExportRequest) -> dict[str, Any]:
        return operations.export_png(storage, request)

    @app.post("/api/exports/svg")
    def export_svg(request: SvgExportRequest) -> dict[str, Any]:
        return operations.export_svg(storage, request, max_dimension=settings.vector_max_dimension)

    @app.post("/api/exports/cut")
    def export_cut(request: PngExportRequest) -> dict[str, Any]:
        return operations.export_cut_svg(storage, request)

    @app.post("/api/exports/zip")
    def export_zip(request: ZipExportRequest) -> dict[str, Any]:
        return operations.export_zip(storage, request, max_dimension=settings.vector_max_dimension)

    @app.post("/api/exports/sheet/layout")
    def sheet_layout(request: SheetRequest) -> dict[str, Any]:
        return operations.layout_sheet(request)

    @app.post("/api/exports/sheet")
    def sheet(request: SheetRequest) -> dict[str, Any]:
        return operations.export_sheet(storage, request)

    @app.post("/api/jobs")
    def create_job(request: JobCreateRequest) -> dict[str, str]:
        kind = request.kind

        def fn(progress: Any) -> dict[str, Any]:
            if kind == "restore":
                if request.restore is None:
                    raise ValueError("A restore job needs restore settings.")
                return operations.restore_upload(storage, settings, request.restore, progress)
            if kind == "vectorize":
                if request.vectorize is None:
                    raise ValueError("A vectorize job needs vector settings.")
                return operations.vectorize_artifact(
                    storage, request.vectorize, progress, max_dimension=settings.vector_max_dimension
                )
            if kind == "export_png":
                if request.png is None:
                    raise ValueError("A PNG export job needs an artifact and appearance.")
                return operations.export_png(storage, request.png, progress)
            if kind == "export_svg":
                if request.svg is None:
                    raise ValueError("An SVG export job needs an artifact and appearance.")
                return operations.export_svg(storage, request.svg, progress, max_dimension=settings.vector_max_dimension)
            if kind == "export_zip":
                if request.zip is None:
                    raise ValueError("A ZIP export job needs an artifact and appearance.")
                return operations.export_zip(storage, request.zip, progress, max_dimension=settings.vector_max_dimension)
            if request.sheet is None:
                raise ValueError("A sheet job needs items and a page size.")
            return operations.export_sheet(storage, request.sheet, progress)

        job_id = jobs.submit(kind, fn)
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="That processing job was not found.")
        return record

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        record = jobs.cancel(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="That processing job was not found.")
        return record

    @app.get("/api/artifacts/{artifact_id}")
    def artifact(artifact_id: str, download: int = 0) -> Response:
        data, record = storage.artifact_bytes(artifact_id)
        suffix = record.get("suffix", ".png")
        media = MEDIA_TYPES.get(suffix, mimetypes.guess_type(f"file{suffix}")[0] or "application/octet-stream")
        filename = record.get("filename") or f"sticky-{artifact_id[:8]}{suffix}"
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        }
        if suffix == ".svg":
            headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
        return Response(content=data, media_type=media, headers=headers)

    return app


app = create_app()
