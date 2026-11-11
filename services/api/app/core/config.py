"""Runtime configuration.

Every external choice is an environment variable. Nothing here enables
telemetry or a hosted model API.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STICKY_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Path("/tmp/sticky-data")
    max_upload_mb: int = 25
    max_megapixels: float = 40
    preview_max_dimension: int = 1400
    final_max_dimension: int = 4096
    vector_max_dimension: int = 1200
    artifact_ttl_hours: float = 6
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    segmentation_backend: str = "opencv"
    enable_rembg: bool = False
    job_workers: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def max_pixels(self) -> int:
        return int(self.max_megapixels * 1_000_000)
