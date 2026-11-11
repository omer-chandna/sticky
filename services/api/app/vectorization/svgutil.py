"""SVG post-processing and a strict sanitizer.

Previews and downloads only keep vector drawing elements. Scripts, external
links, and XML entity tricks are removed.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import fromstring

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

_ALLOWED_TAGS = {
    "svg",
    "g",
    "path",
    "rect",
    "circle",
    "ellipse",
    "polygon",
    "polyline",
    "line",
    "defs",
    "title",
    "desc",
    "metadata",
    "image",
    "clipPath",
    "mask",
}
_ALLOWED_IMAGE_HREF = re.compile(r"^data:image/png;base64,[A-Za-z0-9+/=\s]+$")


class SvgError(ValueError):
    """The SVG is empty or not safe to preview."""


def sanitize_svg(svg: str, *, allow_embedded_png: bool = False) -> str:
    if len(svg) > 12_000_000:
        raise SvgError("The SVG is too large to preview safely.")
    lowered = svg.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise SvgError("This SVG contains a document type Sticky will not render.")
    try:
        root = fromstring(svg.encode("utf-8"))
    except ET.ParseError as exc:
        raise SvgError("The SVG is not valid XML.") from exc
    _clean(root, allow_embedded_png=allow_embedded_png)
    if _local(root.tag) != "svg":
        raise SvgError("The SVG root element is missing.")
    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


def count_paths(svg: str) -> int:
    return len(re.findall(r"<(?:\w+:)?path\b", svg))


def has_embedded_image(svg: str) -> bool:
    return bool(re.search(r"<(?:\w+:)?image\b", svg))


def set_svg_size(svg: str, *, width_mm: float, height_mm: float, view_width: float, view_height: float, description: str, mode: str) -> str:
    root = fromstring(sanitize_svg(svg, allow_embedded_png=True).encode("utf-8"))
    root.set("width", f"{width_mm:.3f}mm")
    root.set("height", f"{height_mm:.3f}mm")
    root.set("viewBox", f"0 0 {view_width:.3f} {view_height:.3f}")
    root.set("data-sticky-mode", mode)
    desc = ET.Element(f"{{{SVG_NS}}}desc")
    desc.text = description
    root.insert(0, desc)
    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


def _clean(element: ET.Element, *, allow_embedded_png: bool) -> None:
    if _local(element.tag) not in _ALLOWED_TAGS:
        element.tag = f"{{{SVG_NS}}}g"
        element.attrib.clear()
        element.text = None
    if _local(element.tag) == "image" and not allow_embedded_png:
        element.tag = f"{{{SVG_NS}}}g"
        element.attrib.clear()
    attribs = list(element.attrib.items())
    for key, value in attribs:
        local = _local(key)
        if local.lower().startswith("on") or local.lower() in {"script", "style"}:
            del element.attrib[key]
            continue
        if local in {"href", "xlink:href"} or key.endswith("}href"):
            if not (allow_embedded_png and _ALLOWED_IMAGE_HREF.match(value.strip())):
                if not value.startswith("#"):
                    del element.attrib[key]
    for child in list(element):
        if _local(child.tag) not in _ALLOWED_TAGS:
            element.remove(child)
            continue
        _clean(child, allow_embedded_png=allow_embedded_png)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
