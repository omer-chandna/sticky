import type {
  DetectResponse,
  ExportResponse,
  RestoreResponse,
  SheetResponse,
  UploadResponse,
  VectorResponse,
} from "@sticky/shared";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_URL}${path}`;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join(" ");
    }
  } catch {
    /* The body was not JSON. */
  }
  return "Sticky could not finish that step.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<T>;
}

export function uploadImage(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return request("/api/uploads", { method: "POST", body });
}

export function getUpload(uploadId: string): Promise<UploadResponse> {
  return request(`/api/uploads/${uploadId}`);
}

export function deleteUpload(uploadId: string): Promise<void> {
  return request(`/api/uploads/${uploadId}`, { method: "DELETE" });
}

export function detectStickers(uploadId: string, mode: "single" | "collection"): Promise<DetectResponse> {
  return request("/api/detect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, mode, min_area_ratio: mode === "collection" ? 0.008 : 0.012 }),
  });
}

export type RestoreBody = {
  upload_id: string;
  quality?: "preview" | "final";
  prepared_artifact_id?: string;
  geometry: {
    polygon?: { x: number; y: number }[] | null;
    quad?: { x: number; y: number }[] | null;
    apply_perspective?: boolean;
    mask_png_base64?: string | null;
    authoritative_mask?: boolean;
  };
  segment?: { refinement?: number; feather?: number; backend?: "opencv" | "rembg" };
  restore?: Record<string, number | boolean>;
};

export function restoreSticker(body: RestoreBody): Promise<RestoreResponse> {
  return request("/api/process/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function vectorizeSticker(body: Record<string, unknown>): Promise<VectorResponse> {
  return request("/api/process/vectorize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function requestCutline(body: Record<string, unknown>) {
  return request<{ path_d: string; view_width: number; view_height: number; closed: boolean; point_count: number; holes: number; warnings: string[] }>(
    "/api/process/cutline",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  );
}

export function exportPng(body: Record<string, unknown>): Promise<ExportResponse> {
  return request("/api/exports/png", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function exportSvg(body: Record<string, unknown>): Promise<ExportResponse> {
  return request("/api/exports/svg", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function exportCut(body: Record<string, unknown>): Promise<ExportResponse> {
  return request("/api/exports/cut", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function exportZip(body: Record<string, unknown>): Promise<ExportResponse> {
  return request("/api/exports/zip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function layoutSheet(body: Record<string, unknown>): Promise<SheetResponse> {
  return request("/api/exports/sheet/layout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function exportSheet(body: Record<string, unknown>): Promise<SheetResponse> {
  return request("/api/exports/sheet", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

type JobRecord = {
  job_id: string;
  status: string;
  stage: string;
  stages_completed: string[];
  result: Record<string, unknown> | null;
  error: string | null;
};

export async function runJob(
  body: Record<string, unknown>,
  onStage: (stage: string) => void,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const created = await request<{ job_id: string }>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  for (;;) {
    if (signal?.aborted) {
      await request(`/api/jobs/${created.job_id}/cancel`, { method: "POST" }).catch(() => undefined);
      throw new Error("Cancelled.");
    }
    const job = await request<JobRecord>(`/api/jobs/${created.job_id}`);
    onStage(job.stage);
    if (job.status === "completed" && job.result) return job.result;
    if (job.status === "failed") throw new Error(job.error || "Sticky could not finish that step.");
    if (job.status === "cancelled") throw new Error("Cancelled.");
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await fetch(apiUrl(path));
  if (!response.ok) throw new Error(await readError(response));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
