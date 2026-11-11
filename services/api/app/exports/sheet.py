"""Millimetre sheet layout.

Packing uses each sticker's occupied bounding box. Irregular artworks still
reserve that full box, plus the requested gap, so automatic placement does
not overlap. Users can move items afterward.
"""

from __future__ import annotations

from dataclasses import dataclass, field


PAGE_SIZES_MM = {
    "letter": (215.9, 279.4),
    "a4": (210.0, 297.0),
}


@dataclass
class SheetItem:
    id: str
    width_mm: float
    height_mm: float
    x_mm: float = 0
    y_mm: float = 0
    rotation_deg: float = 0


@dataclass
class SheetSpec:
    page: str = "letter"
    orientation: str = "portrait"
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None
    margin_mm: float = 12
    spacing_mm: float = 4
    calibration_square: bool = False


@dataclass
class PlacedItem:
    id: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    rotation_deg: float = 0


@dataclass
class LayoutResult:
    page_width_mm: float
    page_height_mm: float
    items: list[PlacedItem] = field(default_factory=list)
    overflows: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def page_size_mm(spec: SheetSpec) -> tuple[float, float]:
    if spec.page == "custom":
        if not spec.custom_width_mm or not spec.custom_height_mm:
            raise ValueError("A custom page needs a width and a height in millimetres.")
        width, height = float(spec.custom_width_mm), float(spec.custom_height_mm)
    else:
        if spec.page not in PAGE_SIZES_MM:
            raise ValueError("Choose Letter, A4, or a custom page size.")
        width, height = PAGE_SIZES_MM[spec.page]
    if spec.orientation == "landscape":
        width, height = max(width, height), min(width, height)
    else:
        width, height = min(width, height), max(width, height)
    return width, height


def pack_sheet(spec: SheetSpec, items: list[SheetItem]) -> LayoutResult:
    page_w, page_h = page_size_mm(spec)
    warnings: list[str] = []
    if spec.margin_mm < 0 or spec.margin_mm * 2 >= min(page_w, page_h):
        raise ValueError("Margins leave no room for stickers on this page.")
    if spec.calibration_square and spec.margin_mm < 14:
        raise ValueError("The 10 mm calibration square needs a margin of at least 14 mm, or turn the square off.")
    usable_right = page_w - spec.margin_mm
    usable_bottom = page_h - spec.margin_mm
    cursor_x = spec.margin_mm
    cursor_y = spec.margin_mm
    row_height = 0.0
    placed: list[PlacedItem] = []
    overflows: list[str] = []
    ordered = sorted(items, key=lambda item: (-item.height_mm, -item.width_mm, item.id))
    for item in ordered:
        # width_mm and height_mm are the occupied bounding box, already including rotation.
        box_w, box_h = item.width_mm, item.height_mm
        if box_w > usable_right - spec.margin_mm + 0.01 or box_h > usable_bottom - spec.margin_mm + 0.01:
            overflows.append(item.id)
            continue
        if cursor_x + box_w > usable_right + 0.01:
            cursor_x = spec.margin_mm
            cursor_y += row_height + spec.spacing_mm
            row_height = 0.0
        if cursor_y + box_h > usable_bottom + 0.01:
            overflows.append(item.id)
            continue
        placed.append(
            PlacedItem(
                id=item.id,
                x_mm=round(cursor_x, 3),
                y_mm=round(cursor_y, 3),
                width_mm=round(box_w, 3),
                height_mm=round(box_h, 3),
                rotation_deg=item.rotation_deg,
            )
        )
        cursor_x += box_w + spec.spacing_mm
        row_height = max(row_height, box_h)
    if overflows:
        warnings.append(
            "Some stickers do not fit on this sheet. Make them smaller, reduce the margin, or move them to another page."
        )
    return LayoutResult(page_w, page_h, placed, overflows, warnings)


def validate_placement(spec: SheetSpec, items: list[PlacedItem], *, allow_overlap: bool = False) -> list[str]:
    page_w, page_h = page_size_mm(spec)
    errors: list[str] = []
    if spec.margin_mm < 0 or spec.margin_mm * 2 >= min(page_w, page_h):
        errors.append("Margins leave no room for stickers on this page.")
    for item in items:
        if item.width_mm <= 0 or item.height_mm <= 0:
            errors.append(f"{item.id} has no printable size.")
            continue
        if item.x_mm < spec.margin_mm - 0.4 or item.y_mm < spec.margin_mm - 0.4:
            errors.append(f"{item.id} crosses the page margin.")
        if item.x_mm + item.width_mm > page_w - spec.margin_mm + 0.4:
            errors.append(f"{item.id} extends past the right margin.")
        if item.y_mm + item.height_mm > page_h - spec.margin_mm + 0.4:
            errors.append(f"{item.id} extends past the bottom margin.")
    if not allow_overlap:
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                if _overlaps(left, right, gap=0.2):
                    errors.append(f"{left.id} overlaps {right.id}.")
    return errors


def _footprint(item: SheetItem) -> tuple[float, float]:
    rotation = abs(item.rotation_deg) % 180
    if abs(rotation - 90) < 0.5:
        return item.height_mm, item.width_mm
    if rotation > 0.5 and abs(rotation - 180) > 0.5:
        radians = np_radians(rotation)
        box_w = abs(item.width_mm * _cos(radians)) + abs(item.height_mm * _sin(radians))
        box_h = abs(item.width_mm * _sin(radians)) + abs(item.height_mm * _cos(radians))
        return box_w, box_h
    return item.width_mm, item.height_mm


def _overlaps(left: PlacedItem, right: PlacedItem, gap: float) -> bool:
    return not (
        left.x_mm + left.width_mm <= right.x_mm + gap
        or right.x_mm + right.width_mm <= left.x_mm + gap
        or left.y_mm + left.height_mm <= right.y_mm + gap
        or right.y_mm + right.height_mm <= left.y_mm + gap
    )


def np_radians(degrees: float) -> float:
    return degrees * 3.141592653589793 / 180.0


def _cos(value: float) -> float:
    import math

    return math.cos(value)


def _sin(value: float) -> float:
    import math

    return math.sin(value)
