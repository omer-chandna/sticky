"""Exact-size PDF sticker sheets.

Page dimensions are real paper sizes in points. Stickers are drawn at their
millimetre boxes. The PDF does not add Cricut registration marks.
"""

from __future__ import annotations

import io

from PIL import Image as PILImage
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.exports.sheet import LayoutResult, PlacedItem, SheetSpec, page_size_mm


def build_sheet_pdf(
    spec: SheetSpec,
    layout: LayoutResult,
    images: dict[str, PILImage.Image],
    *,
    show_guides: bool = False,
) -> bytes:
    page_w, page_h = page_size_mm(spec)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w * mm, page_h * mm))
    pdf.setTitle("Sticky sticker sheet")
    pdf.setAuthor("Sticky")
    for item in layout.items:
        image = images.get(item.id)
        if image is None:
            continue
        _draw_item(pdf, page_h, item, image)
        if show_guides:
            _draw_crop_marks(pdf, page_h, item)
    if spec.calibration_square:
        _draw_calibration(pdf, spec)
    if spec.margin_mm >= 8:
        _draw_print_instruction(pdf, page_w, page_h, spec.margin_mm)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _draw_item(pdf: canvas.Canvas, page_h_mm: float, item: PlacedItem, image: PILImage.Image) -> None:
    reader = ImageReader(image)
    x = item.x_mm * mm
    y = (page_h_mm - item.y_mm - item.height_mm) * mm
    width = item.width_mm * mm
    height = item.height_mm * mm
    rotation = item.rotation_deg % 360
    if abs(rotation) < 0.1 or abs(rotation - 360) < 0.1:
        pdf.drawImage(reader, x, y, width, height, mask="auto", preserveAspectRatio=True, anchor="c")
        return
    pdf.saveState()
    pdf.translate(x + width / 2, y + height / 2)
    pdf.rotate(rotation)
    # The supplied box is already the occupied footprint. Draw the image inside
    # that box without a second rotation of the box itself.
    pdf.drawImage(reader, -width / 2, -height / 2, width, height, mask="auto", preserveAspectRatio=True, anchor="c")
    pdf.restoreState()


def _draw_crop_marks(pdf: canvas.Canvas, page_h_mm: float, item: PlacedItem) -> None:
    x0 = item.x_mm * mm
    y0 = (page_h_mm - item.y_mm - item.height_mm) * mm
    x1 = x0 + item.width_mm * mm
    y1 = y0 + item.height_mm * mm
    mark = 2.2 * mm
    gap = 0.6 * mm
    pdf.setStrokeColorRGB(0.35, 0.35, 0.35)
    pdf.setLineWidth(0.4)
    corners = (
        (x0, y0, -1, -1),
        (x1, y0, 1, -1),
        (x0, y1, -1, 1),
        (x1, y1, 1, 1),
    )
    for origin_x, origin_y, x_sign, y_sign in corners:
        pdf.line(origin_x + x_sign * gap, origin_y, origin_x + x_sign * (gap + mark), origin_y)
        pdf.line(origin_x, origin_y + y_sign * gap, origin_x, origin_y + y_sign * (gap + mark))


def _draw_calibration(pdf: canvas.Canvas, spec: SheetSpec) -> None:
    size = 10 * mm
    x = spec.margin_mm * mm - size - 1.5 * mm
    if x < 1 * mm:
        x = 1.5 * mm
    y = 1.6 * mm
    pdf.setStrokeColorRGB(0.1, 0.1, 0.1)
    pdf.setFillColorRGB(0.1, 0.1, 0.1)
    pdf.setLineWidth(0.6)
    pdf.rect(x, y, size, size, stroke=1, fill=0)
    pdf.setFont("Helvetica", 6)
    pdf.drawString(x, y + size + 1.2 * mm, "10 mm")


def _draw_print_instruction(pdf: canvas.Canvas, page_w: float, page_h: float, margin_mm: float) -> None:
    text = "Print at 100% (Actual Size). Do not use Fit to Page."
    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    pdf.setFont("Helvetica", 8)
    width = pdfmetrics.stringWidth(text, "Helvetica", 8)
    pdf.drawString((page_w * mm - width) / 2, max(2.2 * mm, (margin_mm * mm - 10)), text)
