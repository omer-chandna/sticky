"""Temporary local storage for uploads and derived artifacts.

Paths never leave the server. Clients only receive opaque ids. Files older
than the configured TTL are deleted on startup and by the cleanup loop.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.images import LoadedImage, encode_png


class StorageError(KeyError):
    """The requested upload or artifact is missing or expired."""


class Storage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = Path(settings.data_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_upload(self, loaded: LoadedImage, filename: str) -> dict[str, Any]:
        upload_id = uuid.uuid4().hex
        folder = self._upload_dir(upload_id)
        folder.mkdir(parents=True, exist_ok=False)
        encode_path = folder / "original.png"
        encode_path.write_bytes(encode_png(loaded.rgb))
        height, width = loaded.rgb.shape[:2]
        meta = {
            "upload_id": upload_id,
            "filename": _safe_filename(filename),
            "width": width,
            "height": height,
            "warnings": loaded.warnings,
            "source_format": loaded.source_format,
            "created": time.time(),
        }
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta

    def get_upload(self, upload_id: str) -> dict[str, Any]:
        meta_path = self._upload_dir(upload_id) / "meta.json"
        if not meta_path.is_file():
            raise StorageError("That photo is no longer available. Upload it again.")
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def upload_path(self, upload_id: str) -> Path:
        path = self._upload_dir(upload_id) / "original.png"
        if not path.is_file():
            raise StorageError("That photo is no longer available. Upload it again.")
        return path

    def save_artifact(
        self,
        upload_id: str,
        *,
        kind: str,
        data: bytes,
        meta: dict[str, Any],
        suffix: str,
    ) -> dict[str, Any]:
        self.get_upload(upload_id)
        artifact_id = uuid.uuid4().hex
        folder = self._upload_dir(upload_id) / "artifacts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{artifact_id}{suffix}"
        path.write_bytes(data)
        record = {
            "artifact_id": artifact_id,
            "upload_id": upload_id,
            "kind": kind,
            "suffix": suffix,
            "created": time.time(),
            **meta,
        }
        (folder / f"{artifact_id}.json").write_text(json.dumps(record), encoding="utf-8")
        return record

    def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        found = self._find_artifact(artifact_id)
        if found is None:
            raise StorageError("That processed file is no longer available. Run the step again.")
        return found

    def artifact_bytes(self, artifact_id: str) -> tuple[bytes, dict[str, Any]]:
        record = self.get_artifact(artifact_id)
        path = self._upload_dir(record["upload_id"]) / "artifacts" / f"{artifact_id}{record['suffix']}"
        if not path.is_file():
            raise StorageError("That processed file is no longer available. Run the step again.")
        return path.read_bytes(), record

    def cache_get(self, upload_id: str, key: str) -> dict[str, Any] | None:
        path = self._upload_dir(upload_id) / "cache" / f"{key}.json"
        if not path.is_file():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        artifact_id = record.get("artifact_id")
        if not artifact_id:
            return record
        try:
            self.get_artifact(artifact_id)
        except StorageError:
            return None
        return record

    def cache_put(self, upload_id: str, key: str, record: dict[str, Any]) -> None:
        folder = self._upload_dir(upload_id) / "cache"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{key}.json").write_text(json.dumps(record), encoding="utf-8")

    def delete_upload(self, upload_id: str) -> None:
        folder = self._upload_dir(upload_id)
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)

    def cleanup_expired(self) -> int:
        removed = 0
        ttl = self.settings.artifact_ttl_hours * 3600
        now = time.time()
        if not self.root.exists():
            return 0
        for folder in self.root.iterdir():
            meta_path = folder / "meta.json"
            if not meta_path.is_file():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                created = float(meta.get("created", now))
            except (json.JSONDecodeError, TypeError, ValueError):
                created = now
            if now - created > ttl:
                shutil.rmtree(folder, ignore_errors=True)
                removed += 1
        return removed

    def _upload_dir(self, upload_id: str) -> Path:
        if not _is_opaque_id(upload_id):
            raise StorageError("Unknown photo id.")
        return self.root / upload_id

    def _find_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        if not _is_opaque_id(artifact_id):
            return None
        for meta_path in self.root.glob(f"*/artifacts/{artifact_id}.json"):
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
        return None


def _is_opaque_id(value: str) -> bool:
    return len(value) == 32 and all(char in "0123456789abcdef" for char in value)


def _safe_filename(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ".-_ " else "_" for char in name)
    cleaned = cleaned.strip().strip(".")
    return cleaned[:80] or "sticker"
