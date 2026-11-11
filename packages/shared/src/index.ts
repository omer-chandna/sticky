/** Types shared with the Sticky web app. The API itself is typed in Python. */

export type Point = { x: number; y: number };

export type StickerShape = "rect" | "circle" | "irregular";

export type Candidate = {
  id: string;
  polygon: Point[];
  bbox: { x: number; y: number; width: number; height: number };
  quad: Point[] | null;
  confidence: number;
  shape: StickerShape;
  area_ratio: number;
  perspective_suggested: boolean;
};

export type UploadResponse = {
  upload_id: string;
  filename: string;
  width: number;
  height: number;
  warnings: string[];
  preview_url: string;
};

export type DetectResponse = {
  upload_id: string;
  width: number;
  height: number;
  manual_recommended: boolean;
  warnings: string[];
  candidates: Candidate[];
};

export type Cutline = {
  path_d: string;
  view_width: number;
  view_height: number;
  closed: boolean;
  point_count: number;
  holes: number;
  warnings?: string[];
};

export type RestoreResponse = {
  upload_id: string;
  artifact_id: string;
  prepared_artifact_id: string;
  before_artifact_id: string;
  preview_url: string;
  before_url: string;
  width: number;
  height: number;
  warnings: string[];
  segment_backend: string;
  cutline: Cutline;
};

export type VectorResponse = {
  artifact_id: string;
  preview_url: string;
  svg: string;
  path_count: number;
  width_px: number;
  height_px: number;
  fidelity: number;
  recommend_faithful: boolean;
  byte_size: number;
  preset: string;
  warnings: string[];
};

export type ExportResponse = {
  artifact_id: string;
  download_url: string;
  preview_url?: string;
  filename: string;
  media_type: string;
  warnings?: string[];
  occupied_width_mm?: number;
  occupied_height_mm?: number;
  artwork_width_mm?: number;
  artwork_height_mm?: number;
  fidelity?: number | null;
  recommend_faithful?: boolean;
  path_count?: number;
  mode?: string;
};

export type SheetPlacement = {
  id: string;
  x_mm: number;
  y_mm: number;
  width_mm: number;
  height_mm: number;
  rotation_deg: number;
};

export type SheetResponse = {
  page_width_mm: number;
  page_height_mm: number;
  items: SheetPlacement[];
  overflows: string[];
  warnings: string[];
  artifact_id?: string;
  download_url?: string;
  filename?: string;
};

export type Unit = "mm" | "cm" | "in";

export function toMillimetres(value: number, unit: Unit): number {
  if (unit === "cm") return value * 10;
  if (unit === "in") return value * 25.4;
  return value;
}

export function fromMillimetres(mm: number, unit: Unit): number {
  if (unit === "cm") return mm / 10;
  if (unit === "in") return mm / 25.4;
  return mm;
}

export function pageSizeMm(page: "letter" | "a4", orientation: "portrait" | "landscape"): { width: number; height: number } {
  const base = page === "letter" ? { width: 215.9, height: 279.4 } : { width: 210, height: 297 };
  if (orientation === "landscape") return { width: base.height, height: base.width };
  return base;
}
