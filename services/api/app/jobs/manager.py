"""Small in-process job runner.

Stages are recorded as they actually start. There is no fake percent complete.
Cancellation takes effect between stages; a single OpenCV or VTracer call is
not interrupted.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.core.config import Settings


class JobCancelled(RuntimeError):
    """The client cancelled the job between stages."""


class JobManager:
    def __init__(self, settings: Settings):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max(1, settings.job_workers), thread_name_prefix="sticky-job")

    def submit(self, kind: str, fn: Callable[[Callable[[str], None]], dict]) -> str:
        job_id = uuid.uuid4().hex
        record = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "stage": "queued",
            "stages_completed": [],
            "result": None,
            "error": None,
            "cancel": threading.Event(),
        }
        with self._lock:
            self._jobs[job_id] = record

        def run() -> None:
            def progress(stage: str) -> None:
                with self._lock:
                    if record["cancel"].is_set():
                        record["status"] = "cancelled"
                        record["stage"] = "cancelled"
                        raise JobCancelled("Cancelled")
                    record["status"] = "running"
                    record["stage"] = stage
                    if stage not in record["stages_completed"]:
                        record["stages_completed"].append(stage)

            try:
                result = fn(progress)
                with self._lock:
                    if record["status"] != "cancelled":
                        record["status"] = "completed"
                        record["stage"] = "done"
                        record["result"] = result
            except JobCancelled:
                with self._lock:
                    record["status"] = "cancelled"
                    record["stage"] = "cancelled"
            except Exception as exc:  # noqa: BLE001 - returned to the client as a safe message
                with self._lock:
                    record["status"] = "failed"
                    record["stage"] = "failed"
                    record["error"] = str(exc) or "Sticky could not finish that step."
                    record["trace"] = traceback.format_exc(limit=6)

        self._executor.submit(run)
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return {
                "job_id": record["job_id"],
                "kind": record["kind"],
                "status": record["status"],
                "stage": record["stage"],
                "stages_completed": list(record["stages_completed"]),
                "result": record["result"],
                "error": record["error"],
            }

    def cancel(self, job_id: str) -> dict | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            record["cancel"].set()
            if record["status"] in {"queued", "running"}:
                record["status"] = "cancelled"
                record["stage"] = "cancelled"
        return self.get(job_id)
