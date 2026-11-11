"""Bundle sticker assets with a plain JSON manifest."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Iterable


def build_zip(files: Iterable[tuple[str, bytes]], manifest: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name, data in files:
            safe = name.replace("\\", "/").lstrip("/")
            if ".." in safe.split("/"):
                continue
            archive.writestr(safe, data)
    return buffer.getvalue()
