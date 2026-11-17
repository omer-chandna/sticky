import io

import numpy as np
from PIL import Image

from app.core.images import encode_png
from app.exports.render import Appearance, render_sticker


def _artwork(width: int, height: int) -> np.ndarray:
    art = np.zeros((height, width, 4), np.uint8)
    art[:, :, :3] = 200
    art[10:-10, 10:-10, 3] = 255
    return art


def test_export_keeps_native_detail_when_print_size_is_small():
    # 70 mm at 300 DPI needs ~827 px, but the restore has 1621 px: keep them all.
    rendered = render_sticker(_artwork(1621, 926), Appearance(width_mm=70, height_mm=40))
    assert rendered.image.shape[1] == 1621
    assert abs(rendered.image.shape[0] - 926) <= 1
    assert not any("enlarged" in warning for warning in rendered.warnings)


def test_export_still_enlarges_to_reach_print_dpi():
    rendered = render_sticker(_artwork(400, 400), Appearance(width_mm=70, height_mm=70))
    assert rendered.image.shape[1] == round(70 / 25.4 * 300)
    assert any("enlarged" in warning for warning in rendered.warnings)


def test_png_records_effective_dpi():
    rendered = render_sticker(_artwork(1621, 926), Appearance(width_mm=70, height_mm=40))
    dpi = rendered.image.shape[1] / (rendered.occupied_width_mm / 25.4)
    png = Image.open(io.BytesIO(encode_png(rendered.image, dpi=dpi)))
    assert round(png.info["dpi"][0]) == round(dpi)
    # The physical width stays at the requested 70 mm.
    assert abs(png.width / png.info["dpi"][0] * 25.4 - 70) < 0.2
