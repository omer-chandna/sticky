"""Request and response models shared by the HTTP layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PointModel(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class GeometryModel(BaseModel):
    polygon: list[PointModel] | None = None
    quad: list[PointModel] | None = None
    apply_perspective: bool = False
    mask_png_base64: str | None = None
    authoritative_mask: bool = False

    @field_validator("mask_png_base64")
    @classmethod
    def strip_data_url(cls, value: str | None) -> str | None:
        if value and value.startswith("data:"):
            return value.split(",", 1)[1]
        return value


class SegmentModel(BaseModel):
    refinement: float = Field(40, ge=0, le=100)
    feather: float = Field(0, ge=0, le=100)
    backend: Literal["opencv", "rembg"] = "opencv"


class RestoreModel(BaseModel):
    cleanup_strength: float = Field(25, ge=0, le=100)
    edge_smoothness: float = Field(12, ge=0, le=100)
    color_correction: float = Field(0, ge=0, le=100)
    sharpness: float = Field(8, ge=0, le=100)
    brightness: float = Field(0, ge=-100, le=100)
    contrast: float = Field(0, ge=-100, le=100)
    saturation: float = Field(0, ge=-100, le=100)
    exposure: float = Field(0, ge=-100, le=100)
    denoise: float = Field(0, ge=0, le=100)
    white_balance: float = Field(0, ge=0, le=100)
    clahe: bool = False


class DetectRequest(BaseModel):
    upload_id: str
    mode: Literal["single", "collection"] = "single"
    min_area_ratio: float = Field(0.012, ge=0.001, le=0.5)
    max_candidates: int = Field(24, ge=1, le=48)


class RestoreRequest(BaseModel):
    upload_id: str
    quality: Literal["preview", "final"] = "preview"
    prepared_artifact_id: str | None = None
    geometry: GeometryModel = Field(default_factory=GeometryModel)
    segment: SegmentModel = Field(default_factory=SegmentModel)
    restore: RestoreModel = Field(default_factory=RestoreModel)


class VectorRequest(BaseModel):
    artifact_id: str
    preset: Literal["logo", "illustration", "detailed", "monochrome", "custom"] = "illustration"
    color_complexity: float | None = Field(None, ge=0, le=100)
    curve_smoothness: float | None = Field(None, ge=0, le=100)
    min_region: float | None = Field(None, ge=0, le=100)
    edge_detail: float | None = Field(None, ge=0, le=100)
    noise_filtering: float | None = Field(None, ge=0, le=100)
    path_simplification: float | None = Field(None, ge=0, le=100)


class AppearanceModel(BaseModel):
    width_mm: float = Field(70, gt=5, lt=400)
    height_mm: float = Field(70, gt=5, lt=400)
    background: Literal["transparent", "solid"] = "transparent"
    background_color: str = "#ffffff"
    border_enabled: bool = False
    border_color: str = "#ffffff"
    border_mm: float = Field(2, ge=0, le=25)
    cut_offset_mm: float = Field(0, ge=-8, le=8)
    cut_simplify: float = Field(0.3, ge=0, le=1)
    cut_smooth: float = Field(0.15, ge=0, le=1)
    include_holes: bool = True
    rotation_deg: float = Field(0, ge=-180, le=180)
    flip_h: bool = False
    flip_v: bool = False
    dpi: int = Field(300, ge=72, le=600)
    show_cut_guides: bool = False

    @field_validator("background_color", "border_color")
    @classmethod
    def color(cls, value: str) -> str:
        text = value.strip()
        if not text.startswith("#"):
            text = f"#{text}"
        raw = text[1:]
        if len(raw) not in {3, 6} or any(char not in "0123456789abcdefABCDEF" for char in raw):
            raise ValueError("Colors must be hex values such as #ffffff.")
        return text.lower()


class PngExportRequest(BaseModel):
    artifact_id: str
    appearance: AppearanceModel = Field(default_factory=AppearanceModel)


class SvgExportRequest(BaseModel):
    artifact_id: str
    mode: Literal["vector", "hybrid"] = "hybrid"
    appearance: AppearanceModel = Field(default_factory=AppearanceModel)
    preset: Literal["logo", "illustration", "detailed", "monochrome", "custom"] = "illustration"
    color_complexity: float | None = Field(None, ge=0, le=100)
    curve_smoothness: float | None = Field(None, ge=0, le=100)
    min_region: float | None = Field(None, ge=0, le=100)
    edge_detail: float | None = Field(None, ge=0, le=100)
    noise_filtering: float | None = Field(None, ge=0, le=100)
    path_simplification: float | None = Field(None, ge=0, le=100)


class CutlineRequest(BaseModel):
    artifact_id: str
    width_mm: float = Field(70, gt=5, lt=400)
    height_mm: float = Field(70, gt=5, lt=400)
    offset_mm: float = Field(0, ge=-8, le=8)
    simplify: float = Field(0.3, ge=0, le=1)
    smooth: float = Field(0.15, ge=0, le=1)
    include_holes: bool = True
    border_enabled: bool = False
    border_mm: float = Field(0, ge=0, le=25)


class SheetItemModel(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    artifact_id: str
    x_mm: float = 0
    y_mm: float = 0
    rotation_deg: float = Field(0, ge=-180, le=180)
    appearance: AppearanceModel = Field(default_factory=AppearanceModel)


class SheetRequest(BaseModel):
    page: Literal["letter", "a4", "custom"] = "letter"
    orientation: Literal["portrait", "landscape"] = "portrait"
    custom_width_mm: float | None = Field(None, gt=40, lt=1000)
    custom_height_mm: float | None = Field(None, gt=40, lt=1000)
    margin_mm: float = Field(12, ge=0, le=50)
    spacing_mm: float = Field(4, ge=0, le=40)
    calibration_square: bool = False
    show_guides: bool = False
    auto_pack: bool = True
    allow_overlap: bool = False
    items: list[SheetItemModel] = Field(min_length=1, max_length=40)


class ZipExportRequest(BaseModel):
    artifact_id: str
    mode: Literal["vector", "hybrid"] = "hybrid"
    appearance: AppearanceModel = Field(default_factory=AppearanceModel)
    preset: Literal["logo", "illustration", "detailed", "monochrome", "custom"] = "illustration"
    name: str = "sticker"


class JobCreateRequest(BaseModel):
    kind: Literal["restore", "vectorize", "export_png", "export_svg", "export_zip", "sheet"]
    restore: RestoreRequest | None = None
    vectorize: VectorRequest | None = None
    png: PngExportRequest | None = None
    svg: SvgExportRequest | None = None
    zip: ZipExportRequest | None = None
    sheet: SheetRequest | None = None
