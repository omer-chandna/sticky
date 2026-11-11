import numpy as np
from PIL import Image, ImageDraw

from app.vectorization.svgutil import has_embedded_image, sanitize_svg
from app.vectorization.vtracer_backend import VectorConfig, vectorize_image
from app.tests.fixtures import flat_logo, gradient_badge


def test_flat_logo_becomes_real_paths():
    result = vectorize_image(flat_logo(), VectorConfig(preset="logo", max_dimension=400))
    assert result.path_count >= 2
    assert "<path" in result.svg
    assert not has_embedded_image(result.svg)
    assert result.fidelity > 0.85
    assert result.recommend_faithful is False
    assert 'width="' in result.svg or "<svg" in result.svg


def test_multiple_colors_and_a_thin_line_survive_detailed_settings():
    image = np.zeros((180, 240, 4), np.uint8)
    image[20:160, 20:100] = (20, 80, 200, 255)
    image[20:160, 120:210] = (230, 180, 20, 255)
    image[90:96, 30:200] = (10, 10, 10, 255)
    result = vectorize_image(
        image,
        VectorConfig(
            preset="detailed",
            color_complexity=80,
            noise_filtering=0,
            min_region=0,
            edge_detail=90,
            max_dimension=400,
        ),
    )
    assert result.path_count >= 2
    assert not has_embedded_image(result.svg)


def test_gradient_is_not_presented_as_equivalent():
    result = vectorize_image(gradient_badge(), VectorConfig(preset="detailed", max_dimension=300))
    assert result.path_count >= 1
    assert result.recommend_faithful is True or result.fidelity < 0.9


def test_svg_sanitizer_strips_scripts_and_external_links():
    dirty = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">
      <script>alert(1)</script>
      <image href="https://evil.example/x.png"/>
      <path d="M0 0 L10 0 L10 10 Z" onclick="alert(1)" fill="#fff"/>
    </svg>
    """
    clean = sanitize_svg(dirty, allow_embedded_png=False)
    assert "<script" not in clean.lower()
    assert "evil.example" not in clean
    assert "onclick" not in clean.lower()
    assert "<path" in clean


def test_small_text_reports_a_fidelity_score():
    canvas = Image.new("RGBA", (240, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((8, 8, 232, 72), fill=(255, 255, 255, 255))
    draw.text((16, 28), "STICKY", fill=(0, 0, 0, 255))
    result = vectorize_image(np.array(canvas), VectorConfig(preset="detailed", max_dimension=300))
    assert 0 <= result.fidelity <= 1
    assert result.path_count >= 1
