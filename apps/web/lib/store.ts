"use client";

import type { Point } from "@sticky/shared";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Stage = "select" | "restore" | "reconstruct" | "finish" | "sheet";
export type Tool = "select" | "rect" | "polygon" | "quad" | "brush" | "erase";
export type Unit = "mm" | "cm" | "in";

export type RestoreSettings = {
  cleanup_strength: number;
  edge_smoothness: number;
  color_correction: number;
  sharpness: number;
  background_refinement: number;
  brightness: number;
  contrast: number;
  saturation: number;
  exposure: number;
  denoise: number;
  white_balance: number;
  clahe: boolean;
};

export type VectorControls = {
  color_complexity: number;
  curve_smoothness: number;
  min_region: number;
  edge_detail: number;
  noise_filtering: number;
  path_simplification: number;
};

export type Appearance = {
  unit: Unit;
  widthMm: number;
  heightMm: number;
  lockAspect: boolean;
  rotation: number;
  flipH: boolean;
  flipV: boolean;
  background: "transparent" | "solid";
  backgroundColor: string;
  borderEnabled: boolean;
  borderColor: string;
  borderMm: number;
  cutOffsetMm: number;
  cutSimplify: number;
  cutSmooth: number;
  includeHoles: boolean;
  showCutPreview: boolean;
};

export type StickerItem = {
  id: string;
  name: string;
  detectedPolygon: Point[];
  polygon: Point[];
  quad: Point[] | null;
  usePerspective: boolean;
  shape: string;
  confidence: number;
  brushDataUrl: string | null;
  authoritativeMask: boolean;
  artifactId?: string;
  preparedId?: string;
  beforeUrl?: string;
  previewUrl?: string;
  pixelWidth?: number;
  pixelHeight?: number;
  warnings: string[];
  cutlinePath?: string;
  cutlineView?: { width: number; height: number };
  vectorArtifactId?: string;
  vectorPreviewUrl?: string;
  vectorPathCount?: number;
  vectorFidelity?: number;
  vectorRecommendFaithful?: boolean;
  vectorBytes?: number;
  vectorWarnings?: string[];
  mode: "faithful" | "vector";
  vectorPreset: "logo" | "illustration" | "detailed" | "monochrome";
  vectorControls: VectorControls;
  restore: RestoreSettings;
  appearance: Appearance;
};

export type SheetItem = {
  key: string;
  stickerId: string;
  xMm: number;
  yMm: number;
  rotation: number;
};

type Snapshot = {
  stickers: StickerItem[];
  activeId: string | null;
  sheet: SheetItem[];
};

type ProjectState = {
  uploadId: string | null;
  sourceName: string;
  sourceWidth: number;
  sourceHeight: number;
  sourceUrl: string;
  mode: "single" | "collection";
  stage: Stage;
  tool: Tool;
  stickers: StickerItem[];
  activeId: string | null;
  selectedIds: string[];
  warnings: string[];
  sheet: SheetItem[];
  page: "letter" | "a4";
  orientation: "portrait" | "landscape";
  marginMm: number;
  spacingMm: number;
  calibration: boolean;
  guides: boolean;
  past: Snapshot[];
  future: Snapshot[];
  setStage: (stage: Stage) => void;
  setTool: (tool: Tool) => void;
  setMode: (mode: "single" | "collection") => void;
  setUpload: (upload: { id: string; name: string; width: number; height: number; url: string }) => void;
  setWarnings: (warnings: string[]) => void;
  setStickers: (stickers: StickerItem[], activeId?: string | null) => void;
  updateSticker: (id: string, patch: Partial<StickerItem>, remember?: boolean) => void;
  setActive: (id: string) => void;
  toggleSelected: (id: string) => void;
  setSelected: (ids: string[]) => void;
  pushHistory: () => void;
  undo: () => void;
  redo: () => void;
  setSheet: (sheet: SheetItem[]) => void;
  updateSheetItem: (key: string, patch: Partial<SheetItem>) => void;
  setPage: (page: "letter" | "a4") => void;
  setOrientation: (orientation: "portrait" | "landscape") => void;
  setMargin: (marginMm: number) => void;
  setSpacing: (spacingMm: number) => void;
  setCalibration: (calibration: boolean) => void;
  setGuides: (guides: boolean) => void;
  resetProject: () => void;
};

export const defaultRestore = (): RestoreSettings => ({
  cleanup_strength: 25,
  edge_smoothness: 12,
  color_correction: 0,
  sharpness: 8,
  background_refinement: 40,
  brightness: 0,
  contrast: 0,
  saturation: 0,
  exposure: 0,
  denoise: 0,
  white_balance: 0,
  clahe: false,
});

export const defaultVectorControls = (): VectorControls => ({
  color_complexity: 74,
  curve_smoothness: 55,
  min_region: 16,
  edge_detail: 70,
  noise_filtering: 12,
  path_simplification: 28,
});

export const defaultAppearance = (): Appearance => ({
  unit: "mm",
  widthMm: 70,
  heightMm: 70,
  lockAspect: true,
  rotation: 0,
  flipH: false,
  flipV: false,
  background: "transparent",
  backgroundColor: "#ffffff",
  borderEnabled: false,
  borderColor: "#ffffff",
  borderMm: 2,
  cutOffsetMm: 0,
  cutSimplify: 0.3,
  cutSmooth: 0.15,
  includeHoles: true,
  showCutPreview: true,
});

const empty = {
  uploadId: null as string | null,
  sourceName: "Untitled",
  sourceWidth: 0,
  sourceHeight: 0,
  sourceUrl: "",
  mode: "single" as const,
  stage: "select" as Stage,
  tool: "select" as Tool,
  stickers: [] as StickerItem[],
  activeId: null as string | null,
  selectedIds: [] as string[],
  warnings: [] as string[],
  sheet: [] as SheetItem[],
  page: "letter" as const,
  orientation: "portrait" as const,
  marginMm: 12,
  spacingMm: 4,
  calibration: false,
  guides: false,
  past: [] as Snapshot[],
  future: [] as Snapshot[],
};

function snapshot(state: ProjectState): Snapshot {
  return {
    stickers: structuredClone(state.stickers),
    activeId: state.activeId,
    sheet: structuredClone(state.sheet),
  };
}

export const useProject = create<ProjectState>()(
  persist(
    (set, get) => ({
      ...empty,
      setStage: (stage) => set({ stage }),
      setTool: (tool) => set({ tool }),
      setMode: (mode) => set({ mode, stage: "select" }),
      setUpload: ({ id, name, width, height, url }) =>
        set({
          ...empty,
          uploadId: id,
          sourceName: name,
          sourceWidth: width,
          sourceHeight: height,
          sourceUrl: url,
          past: [],
          future: [],
        }),
      setWarnings: (warnings) => set({ warnings }),
      setStickers: (stickers, activeId) =>
        set({
          stickers,
          activeId: activeId === undefined ? stickers[0]?.id ?? null : activeId,
          selectedIds: stickers[0] ? [stickers[0].id] : [],
        }),
      updateSticker: (id, patch, remember) => {
        if (remember) get().pushHistory();
        set({
          stickers: get().stickers.map((sticker) => (sticker.id === id ? { ...sticker, ...patch } : sticker)),
        });
      },
      setActive: (id) => set({ activeId: id, stage: get().stage === "select" ? "select" : get().stage }),
      toggleSelected: (id) => {
        const selected = new Set(get().selectedIds);
        if (selected.has(id)) selected.delete(id);
        else selected.add(id);
        set({ selectedIds: [...selected], activeId: id });
      },
      setSelected: (ids) => set({ selectedIds: ids }),
      pushHistory: () => {
        const past = [...get().past, snapshot(get())].slice(-30);
        set({ past, future: [] });
      },
      undo: () => {
        const past = [...get().past];
        const previous = past.pop();
        if (!previous) return;
        set({
          past,
          future: [snapshot(get()), ...get().future].slice(0, 30),
          stickers: previous.stickers,
          activeId: previous.activeId,
          sheet: previous.sheet,
        });
      },
      redo: () => {
        const [next, ...future] = get().future;
        if (!next) return;
        set({
          future,
          past: [...get().past, snapshot(get())].slice(-30),
          stickers: next.stickers,
          activeId: next.activeId,
          sheet: next.sheet,
        });
      },
      setSheet: (sheet) => set({ sheet }),
      updateSheetItem: (key, patch) =>
        set({ sheet: get().sheet.map((item) => (item.key === key ? { ...item, ...patch } : item)) }),
      setPage: (page) => set({ page }),
      setOrientation: (orientation) => set({ orientation }),
      setMargin: (marginMm) => set({ marginMm }),
      setSpacing: (spacingMm) => set({ spacingMm }),
      setCalibration: (calibration) => set({ calibration }),
      setGuides: (guides) => set({ guides }),
      resetProject: () => set({ ...empty }),
    }),
    {
      name: "sticky-project-v1",
      partialize: (state) => ({
        uploadId: state.uploadId,
        sourceName: state.sourceName,
        sourceWidth: state.sourceWidth,
        sourceHeight: state.sourceHeight,
        sourceUrl: state.sourceUrl,
        mode: state.mode,
        stage: state.stage,
        stickers: state.stickers.map((sticker) => ({ ...sticker, brushDataUrl: null })),
        activeId: state.activeId,
        selectedIds: state.selectedIds,
        sheet: state.sheet,
        page: state.page,
        orientation: state.orientation,
        marginMm: state.marginMm,
        spacingMm: state.spacingMm,
        calibration: state.calibration,
        guides: state.guides,
      }),
    },
  ),
);

export function appearancePayload(appearance: Appearance) {
  return {
    width_mm: Math.round(appearance.widthMm * 100) / 100,
    height_mm: Math.round(appearance.heightMm * 100) / 100,
    background: appearance.background,
    background_color: appearance.backgroundColor,
    border_enabled: appearance.borderEnabled,
    border_color: appearance.borderColor,
    border_mm: appearance.borderMm,
    cut_offset_mm: appearance.cutOffsetMm,
    cut_simplify: appearance.cutSimplify,
    cut_smooth: appearance.cutSmooth,
    include_holes: appearance.includeHoles,
    rotation_deg: appearance.rotation,
    flip_h: appearance.flipH,
    flip_v: appearance.flipV,
    dpi: 300,
    show_cut_guides: false,
  };
}

export function occupiedSize(appearance: Appearance) {
  const extra = appearance.borderEnabled ? appearance.borderMm * 2 : 0;
  const width = appearance.widthMm + extra;
  const height = appearance.heightMm + extra;
  const radians = (appearance.rotation * Math.PI) / 180;
  return {
    width: Math.abs(width * Math.cos(radians)) + Math.abs(height * Math.sin(radians)),
    height: Math.abs(width * Math.sin(radians)) + Math.abs(height * Math.cos(radians)),
  };
}
