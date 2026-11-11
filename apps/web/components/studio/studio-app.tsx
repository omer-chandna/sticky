"use client";

import type { Point } from "@sticky/shared";
import { fromMillimetres, pageSizeMm, toMillimetres } from "@sticky/shared";
import {
  Crop,
  Eraser,
  FlipHorizontal,
  FlipVertical,
  Github,
  Hexagon,
  MousePointer2,
  Paintbrush,
  Redo2,
  RotateCcw,
  Square,
  Trash2,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { SelectionCanvas } from "@/components/studio/selection-canvas";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { LabeledSlider } from "@/components/ui/slider";
import { Wordmark } from "@/components/wordmark";
import {
  API_URL,
  apiUrl,
  deleteUpload,
  detectStickers,
  downloadFile,
  exportCut,
  exportPng,
  exportSheet,
  exportSvg,
  exportZip,
  getUpload,
  layoutSheet,
  requestCutline,
  runJob,
  uploadImage,
} from "@/lib/api";
import { takePendingFile } from "@/lib/pending";
import {
  appearancePayload,
  defaultAppearance,
  defaultRestore,
  defaultVectorControls,
  occupiedSize,
  useProject,
  type Appearance,
  type StickerItem,
  type VectorControls,
} from "@/lib/store";
import { STAGE_LABELS, cn, formatBytes } from "@/lib/utils";

const STAGES = [
  ["select", "Select"],
  ["restore", "Restore"],
  ["reconstruct", "Vector"],
  ["finish", "Size"],
  ["sheet", "Sheet"],
] as const;

const TOOLS = [
  ["select", "Select", MousePointer2],
  ["rect", "Rectangle", Square],
  ["polygon", "Polygon", Hexagon],
  ["quad", "Corners", Crop],
  ["brush", "Brush", Paintbrush],
  ["erase", "Erase", Eraser],
] as const;

export function StudioApp() {
  const project = useProject();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cutPreview, setCutPreview] = useState<string>("");
  const started = useRef(false);
  const active = project.stickers.find((sticker) => sticker.id === project.activeId) ?? null;

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const boot = () => {
      const file = takePendingFile();
      const mode = sessionStorage.getItem("sticky-mode");
      if (file) {
        void ingest(file, mode === "collection" ? "collection" : "single");
        return;
      }
      const uploadId = useProject.getState().uploadId;
      if (uploadId) {
        getUpload(uploadId).catch(() => {
          setError("That photo is no longer on the Sticky server. Upload it again.");
        });
      }
    };
    if (useProject.persist.hasHydrated()) boot();
    else return useProject.persist.onFinishHydration(boot);
    // Boot once, after local project settings have loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ingest(file: File, mode: "single" | "collection" = project.mode) {
    setError(null);
    setBusy("Loading photo");
    try {
      const uploaded = await uploadImage(file);
      project.setUpload({
        id: uploaded.upload_id,
        name: file.name.replace(/\.[^.]+$/, "") || "Sticker",
        width: uploaded.width,
        height: uploaded.height,
        url: uploaded.preview_url,
      });
      project.setMode(mode);
      if (uploaded.warnings.length) project.setWarnings(uploaded.warnings);
      await runDetect(uploaded.upload_id, mode);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The photo could not be uploaded.");
    } finally {
      setBusy(null);
    }
  }

  async function runDetect(uploadId = project.uploadId, mode = project.mode) {
    if (!uploadId) return;
    setBusy("Detecting sticker");
    setError(null);
    try {
      const detected = await detectStickers(uploadId, mode);
      const stickers = detected.candidates.map((candidate, index) =>
        makeSticker(candidate, index, useProject.getState().sourceName || "Sticker"),
      );
      project.setStickers(stickers);
      project.setWarnings(detected.warnings);
      project.setStage("select");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Detection failed. Draw a selection instead.");
      project.setStickers([
        makeSticker(
          {
            id: "manual",
            polygon: [
              { x: 0.08, y: 0.08 },
              { x: 0.92, y: 0.08 },
              { x: 0.92, y: 0.92 },
              { x: 0.08, y: 0.92 },
            ],
            quad: null,
            confidence: 0,
            shape: "irregular",
            perspective_suggested: false,
          },
          0,
          "Manual selection",
        ),
      ]);
    } finally {
      setBusy(null);
    }
  }

  async function restoreOne(sticker: StickerItem, quality: "preview" | "final" = "preview") {
    if (!project.uploadId) throw new Error("Upload a photo first.");
    const usePrepared = Boolean(sticker.preparedId) && !sticker.brushDataUrl && quality === "preview";
    const result = (await runJob(
      {
        kind: "restore",
        restore: {
          upload_id: project.uploadId,
          quality,
          prepared_artifact_id: usePrepared ? sticker.preparedId : undefined,
          geometry: {
            polygon: usePrepared ? null : sticker.polygon,
            quad: sticker.usePerspective ? sticker.quad : null,
            apply_perspective: Boolean(sticker.usePerspective && sticker.quad && !usePrepared),
            mask_png_base64: sticker.brushDataUrl,
            authoritative_mask: sticker.authoritativeMask,
          },
          segment: { refinement: sticker.restore.background_refinement, feather: 0, backend: "opencv" },
          restore: {
            cleanup_strength: sticker.restore.cleanup_strength,
            edge_smoothness: sticker.restore.edge_smoothness,
            color_correction: sticker.restore.color_correction,
            sharpness: sticker.restore.sharpness,
            brightness: sticker.restore.brightness,
            contrast: sticker.restore.contrast,
            saturation: sticker.restore.saturation,
            exposure: sticker.restore.exposure,
            denoise: sticker.restore.denoise,
            white_balance: sticker.restore.white_balance,
            clahe: sticker.restore.clahe,
          },
        },
      },
      (stage) => setBusy(STAGE_LABELS[stage] || stage),
    )) as unknown as {
      artifact_id: string;
      prepared_artifact_id: string;
      before_url: string;
      preview_url: string;
      width: number;
      height: number;
      warnings: string[];
      cutline: { path_d: string; view_width: number; view_height: number };
    };
    const aspect = result.height / Math.max(result.width, 1);
    project.updateSticker(sticker.id, {
      artifactId: result.artifact_id,
      preparedId: result.prepared_artifact_id,
      beforeUrl: result.before_url,
      previewUrl: result.preview_url,
      pixelWidth: result.width,
      pixelHeight: result.height,
      warnings: result.warnings,
      cutlinePath: result.cutline.path_d,
      cutlineView: { width: result.cutline.view_width, height: result.cutline.view_height },
      brushDataUrl: null,
      authoritativeMask: false,
      appearance: sticker.appearance.lockAspect
        ? { ...sticker.appearance, heightMm: Math.round(sticker.appearance.widthMm * aspect * 10) / 10 }
        : sticker.appearance,
    });
  }

  async function restoreSelected() {
    const ids = project.mode === "collection" ? project.selectedIds : project.activeId ? [project.activeId] : [];
    if (!ids.length) {
      setError("Select at least one sticker, or draw a rectangle around it.");
      return;
    }
    setError(null);
    try {
      for (const id of ids) {
        const sticker = useProject.getState().stickers.find((item) => item.id === id);
        if (sticker) await restoreOne(sticker);
      }
      project.setStage("restore");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Restoration failed. Your photo is still here.");
    } finally {
      setBusy(null);
    }
  }

  async function vectorizeActive(preset?: StickerItem["vectorPreset"], controls?: VectorControls) {
    if (!active?.artifactId) {
      setError("Restore the sticker before vectorizing it.");
      return;
    }
    const chosen = preset ?? active.vectorPreset;
    const knobs = controls ?? active.vectorControls;
    setError(null);
    try {
      const result = (await runJob(
        {
          kind: "vectorize",
          vectorize: {
            artifact_id: active.artifactId,
            preset: chosen,
            ...knobs,
          },
        },
        (stage) => setBusy(STAGE_LABELS[stage] || stage),
      )) as unknown as {
        artifact_id: string;
        preview_url: string;
        path_count: number;
        fidelity: number;
        recommend_faithful: boolean;
        byte_size: number;
        warnings: string[];
      };
      project.updateSticker(active.id, {
        vectorArtifactId: result.artifact_id,
        vectorPreviewUrl: result.preview_url,
        vectorPathCount: result.path_count,
        vectorFidelity: result.fidelity,
        vectorRecommendFaithful: result.recommend_faithful,
        vectorBytes: result.byte_size,
        vectorWarnings: result.warnings,
        vectorPreset: chosen,
        vectorControls: knobs,
        mode: result.recommend_faithful ? active.mode : "vector",
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Vectorizing failed.");
    } finally {
      setBusy(null);
    }
  }

  async function refreshCut(sticker: StickerItem) {
    if (!sticker.artifactId) return;
    const cut = await requestCutline({
      artifact_id: sticker.artifactId,
      width_mm: sticker.appearance.widthMm,
      height_mm: sticker.appearance.heightMm,
      offset_mm: sticker.appearance.cutOffsetMm,
      simplify: sticker.appearance.cutSimplify,
      smooth: sticker.appearance.cutSmooth,
      include_holes: sticker.appearance.includeHoles,
      border_enabled: sticker.appearance.borderEnabled,
      border_mm: sticker.appearance.borderEnabled ? sticker.appearance.borderMm : 0,
    });
    setCutPreview(cut.path_d);
  }

  useEffect(() => {
    if (project.stage !== "finish" || !active?.artifactId || !active.appearance.showCutPreview) return;
    const handle = window.setTimeout(() => {
      void refreshCut(active).catch(() => setCutPreview(""));
    }, 250);
    return () => window.clearTimeout(handle);
    // Appearance fields that affect the cut are listed individually.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    project.stage,
    active?.id,
    active?.artifactId,
    active?.appearance.cutOffsetMm,
    active?.appearance.cutSimplify,
    active?.appearance.cutSmooth,
    active?.appearance.includeHoles,
    active?.appearance.borderEnabled,
    active?.appearance.borderMm,
    active?.appearance.showCutPreview,
    active?.appearance.widthMm,
  ]);

  async function downloadExport(kind: "png" | "svg" | "cut" | "zip") {
    if (!active?.artifactId) return;
    setError(null);
    setBusy("Preparing export");
    try {
      const appearance = appearancePayload(active.appearance);
      const common = { artifact_id: active.artifactId, appearance };
      const result =
        kind === "png"
          ? await exportPng(common)
          : kind === "cut"
            ? await exportCut(common)
            : kind === "zip"
              ? await exportZip({ ...common, mode: active.mode === "vector" ? "vector" : "hybrid", preset: active.vectorPreset, name: active.name })
              : await exportSvg({
                  ...common,
                  mode: active.mode === "vector" ? "vector" : "hybrid",
                  preset: active.vectorPreset,
                  ...active.vectorControls,
                });
      if (result.warnings?.length) project.setWarnings(result.warnings);
      await downloadFile(result.download_url, result.filename);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Export failed.");
    } finally {
      setBusy(null);
    }
  }

  const source = project.sourceUrl ? apiUrl(project.sourceUrl) : "";

  return (
    <div className="min-h-screen pb-36 lg:pb-6">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <Link href="/" aria-label="Sticky home">
          <Wordmark className="text-xl" />
        </Link>
        <div className="hidden items-center gap-2 sm:flex">
          <Button size="sm" variant={project.mode === "single" ? "primary" : "secondary"} onClick={() => void changeMode("single")}>
            Single sticker
          </Button>
          <Button size="sm" variant={project.mode === "collection" ? "primary" : "secondary"} onClick={() => void changeMode("collection")}>
            Collection
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button size="icon" variant="ghost" onClick={() => project.undo()} aria-label="Undo" disabled={!project.past.length}>
            <Undo2 size={18} />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => project.redo()} aria-label="Redo" disabled={!project.future.length}>
            <Redo2 size={18} />
          </Button>
          <Link href="/guide" className="hidden rounded-full px-3 py-2 text-sm sm:inline hover:bg-black/5 dark:hover:bg-white/10">
            Guide
          </Link>
          <a href="https://github.com/omer-chandna/sticky" className="hidden rounded-full p-2 sm:inline" aria-label="Source code">
            <Github size={18} />
          </a>
          <ThemeToggle />
        </div>
      </header>

      {!project.uploadId && (
        <div className="mx-auto max-w-xl px-5 py-16 text-center">
          <h1 className="font-display text-4xl">No photo yet</h1>
          <p className="mt-3 text-muted">Upload a sticker photograph to start. You can also go back and try an example.</p>
          <label className="mt-6 inline-block">
            <span className="sr-only">Upload a photograph</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void ingest(file);
              }}
            />
            <span className="inline-flex h-11 cursor-pointer items-center rounded-full bg-accent px-4 text-sm text-accent-ink">Choose a photo</span>
          </label>
          {error && <p className="mt-4 text-sm text-warn">{error}</p>}
        </div>
      )}

      {project.uploadId && (
        <div className="grid gap-4 px-3 py-4 lg:grid-cols-[220px_minmax(0,1fr)_320px] lg:px-4">
          <aside className="hidden lg:block">
            <StageList stage={project.stage} onChange={project.setStage} />
            <StickerList />
          </aside>
          <main className="min-w-0">
            {busy && (
              <p className="mb-3 rounded-full bg-elev px-4 py-2 text-sm" role="status">
                {busy}
              </p>
            )}
            {error && (
              <p className="mb-3 rounded-2xl border border-warn/40 bg-elev px-4 py-3 text-sm text-warn" role="alert">
                {error}
              </p>
            )}
            {project.warnings.length > 0 && project.stage !== "sheet" && (
              <ul className="mb-3 space-y-1 text-sm text-warn">
                {project.warnings.slice(0, 3).map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
            {project.stage === "select" && source && (
              <div className="overflow-hidden rounded-3xl border border-line bg-elev">
                <SelectionCanvas
                  src={source}
                  stickers={project.stickers}
                  activeId={project.activeId}
                  selectedIds={project.mode === "collection" ? project.selectedIds : project.activeId ? [project.activeId] : []}
                  tool={project.tool}
                  onToggle={(id) => {
                    if (project.mode === "collection") project.toggleSelected(id);
                    else project.setActive(id);
                  }}
                  onChangePolygon={(id, polygon) => project.updateSticker(id, { polygon })}
                  onChangeQuad={(id, quad) => project.updateSticker(id, { quad, usePerspective: true })}
                  onBrush={(dataUrl) => {
                    if (project.activeId) project.updateSticker(project.activeId, { brushDataUrl: dataUrl, authoritativeMask: true });
                  }}
                />
              </div>
            )}
            {project.stage === "restore" && active && <CompareView sticker={active} />}
            {project.stage === "reconstruct" && active && <CompareVector sticker={active} />}
            {project.stage === "finish" && active && (
              <FinishPreview sticker={active} cutPath={cutPreview || active.cutlinePath || ""} />
            )}
            {project.stage === "sheet" && <SheetEditor setBusy={setBusy} setError={setError} />}
            {project.stage === "select" && (
              <div className="mt-3 flex flex-wrap gap-2">
                {TOOLS.map(([id, label, Icon]) => (
                  <Button key={id} size="sm" variant={project.tool === id ? "primary" : "secondary"} onClick={() => project.setTool(id)}>
                    <Icon size={15} /> {label}
                  </Button>
                ))}
              </div>
            )}
          </main>
          <aside className="rounded-3xl border border-line bg-elev p-4">
            {project.stage === "select" && (
              <SelectPanel active={active} onRestore={() => void restoreSelected()} onDetect={() => void runDetect()} />
            )}
            {project.stage === "restore" && active && (
              <RestorePanel
                sticker={active}
                onChange={(restore) => project.updateSticker(active.id, { restore })}
                onCommit={() => {
                  project.pushHistory();
                  const latest = useProject.getState().stickers.find((item) => item.id === active.id);
                  if (!latest) return;
                  void restoreOne(latest).catch((reason: unknown) => {
                    setError(reason instanceof Error ? reason.message : "That adjustment could not be applied.");
                    setBusy(null);
                  });
                }}
              />
            )}
            {project.stage === "reconstruct" && active && (
              <VectorPanel sticker={active} onPreset={(preset) => void vectorizeActive(preset)} onControls={(controls) => void vectorizeActive(active.vectorPreset, controls)} />
            )}
            {project.stage === "finish" && active && (
              <FinishPanel sticker={active} onDownload={(kind) => void downloadExport(kind)} onChange={(appearance) => project.updateSticker(active.id, { appearance })} />
            )}
            {project.stage === "sheet" && <SheetSettings />}
          </aside>
        </div>
      )}

      <nav className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-elev lg:hidden">
        {STAGES.map(([id, label]) => (
          <button key={id} className={cn("flex-1 py-3 text-xs", project.stage === id && "text-accent")} onClick={() => project.setStage(id)}>
            {label}
          </button>
        ))}
      </nav>
      <p className="sr-only">Processing server {API_URL}</p>
    </div>
  );

  async function changeMode(mode: "single" | "collection") {
    project.setMode(mode);
    if (project.uploadId) await runDetect(project.uploadId, mode);
  }
}

function makeSticker(
  candidate: {
    id: string;
    polygon: Point[];
    quad: Point[] | null;
    confidence: number;
    shape: string;
    perspective_suggested: boolean;
  },
  index: number,
  baseName: string,
): StickerItem {
  const quad = candidate.quad ?? (candidate.polygon.length === 4 ? candidate.polygon : null);
  return {
    id: `${candidate.id}-${index}`,
    name: index === 0 ? baseName : `${baseName} ${index + 1}`,
    detectedPolygon: candidate.polygon,
    polygon: candidate.polygon,
    quad,
    usePerspective: candidate.perspective_suggested && Boolean(quad),
    shape: candidate.shape,
    confidence: candidate.confidence,
    brushDataUrl: null,
    authoritativeMask: false,
    warnings: [],
    mode: "faithful",
    vectorPreset: "illustration",
    vectorControls: defaultVectorControls(),
    restore: defaultRestore(),
    appearance: defaultAppearance(),
  };
}

function StageList({ stage, onChange }: { stage: string; onChange: (stage: (typeof STAGES)[number][0]) => void }) {
  return (
    <ol className="space-y-1">
      {STAGES.map(([id, label], index) => (
        <li key={id}>
          <button
            className={cn("flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-left text-sm", stage === id ? "bg-elev" : "hover:bg-elev/70")}
            onClick={() => onChange(id)}
          >
            <span className="text-xs text-muted">{index + 1}</span>
            {label}
          </button>
        </li>
      ))}
    </ol>
  );
}

function StickerList() {
  const stickers = useProject((state) => state.stickers);
  const activeId = useProject((state) => state.activeId);
  const setActive = useProject((state) => state.setActive);
  const update = useProject((state) => state.updateSticker);
  if (!stickers.length) return null;
  return (
    <div className="mt-6 space-y-2">
      <p className="px-2 text-xs uppercase tracking-widest text-muted">Stickers</p>
      {stickers.map((sticker) => (
        <button
          key={sticker.id}
          className={cn("flex w-full items-center gap-2 rounded-2xl px-2 py-2 text-left", sticker.id === activeId && "bg-elev")}
          onClick={() => setActive(sticker.id)}
        >
          <span className="h-10 w-10 overflow-hidden rounded-lg bg-bg">
            {sticker.previewUrl && <img src={apiUrl(sticker.previewUrl)} alt="" className="h-full w-full object-contain" />}
          </span>
          <input
            value={sticker.name}
            aria-label={`Name for ${sticker.name}`}
            className="w-full bg-transparent text-sm"
            onChange={(event) => update(sticker.id, { name: event.target.value })}
            onClick={(event) => event.stopPropagation()}
          />
        </button>
      ))}
    </div>
  );
}

function SelectPanel({
  active,
  onRestore,
  onDetect,
}: {
  active: StickerItem | null;
  onRestore: () => void;
  onDetect: () => void;
}) {
  const project = useProject();
  const [knownWidth, setKnownWidth] = useState(active?.appearance.widthMm ?? 70);
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-2xl">Select</h2>
        <p className="mt-1 text-sm text-muted">
          {active
            ? `${active.shape} · ${Math.round(active.confidence * 100)}% confidence. Drag the outline if it is off.`
            : "Draw a rectangle if nothing was found."}
        </p>
      </div>
      <label className="flex items-center justify-between gap-3 text-sm">
        Straighten with four corners
        <input
          type="checkbox"
          checked={Boolean(active?.usePerspective)}
          onChange={(event) => {
            if (!active) return;
            const quad = active.quad ?? [
              { x: 0.15, y: 0.15 },
              { x: 0.85, y: 0.15 },
              { x: 0.85, y: 0.85 },
              { x: 0.15, y: 0.85 },
            ];
            project.updateSticker(active.id, { usePerspective: event.target.checked, quad });
          }}
        />
      </label>
      <Button variant="primary" className="w-full" onClick={onRestore}>
        Restore {project.mode === "collection" ? "selected" : "sticker"}
      </Button>
      <Button className="w-full" onClick={onDetect}>
        Detect again
      </Button>
      <Button
        className="w-full"
        onClick={() => {
          if (!active) return;
          project.pushHistory();
          project.updateSticker(active.id, { polygon: active.detectedPolygon, brushDataUrl: null, authoritativeMask: false });
        }}
      >
        Reset outline
      </Button>
      <div className="rounded-2xl border border-line p-3 text-sm">
        <p className="font-medium">Intended width</p>
        <p className="mt-1 text-muted">
          A photograph does not contain a scale. If you know how wide this sticker should be, set it here. Perspective correction does not invent that measurement.
        </p>
        <label className="mt-2 block">
          Width in millimetres
          <input
            type="number"
            min={5}
            step={1}
            value={knownWidth}
            onChange={(event) => setKnownWidth(Number(event.target.value))}
            className="mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2"
          />
        </label>
        <Button
          size="sm"
          className="mt-2"
          onClick={() => {
            if (!active || knownWidth < 5) return;
            const ratio = active.appearance.heightMm / Math.max(active.appearance.widthMm, 0.1);
            project.updateSticker(active.id, {
              appearance: {
                ...active.appearance,
                widthMm: knownWidth,
                heightMm: active.appearance.lockAspect ? Math.round(knownWidth * ratio * 10) / 10 : active.appearance.heightMm,
              },
            });
          }}
        >
          Use this width
        </Button>
      </div>
      {project.uploadId && (
        <button
          className="inline-flex items-center gap-2 text-sm text-muted"
          onClick={() => {
            void deleteUpload(project.uploadId!);
            project.resetProject();
          }}
        >
          <Trash2 size={14} /> Remove this photo
        </button>
      )}
    </div>
  );
}

function RestorePanel({
  sticker,
  onChange,
  onCommit,
}: {
  sticker: StickerItem;
  onChange: (restore: StickerItem["restore"]) => void;
  onCommit: () => void;
}) {
  const [advanced, setAdvanced] = useState(false);
  const restore = sticker.restore;
  function set<K extends keyof StickerItem["restore"]>(key: K, value: StickerItem["restore"][K]) {
    onChange({ ...restore, [key]: value });
  }
  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl">Restore</h2>
      <p className="text-sm text-muted">These adjustments start from the original crop every time. They do not stack on top of each other.</p>
      <LabeledSlider label="Cleanup strength" value={restore.cleanup_strength} min={0} max={100} onChange={(value) => set("cleanup_strength", value)} onCommit={onCommit} />
      <LabeledSlider label="Edge smoothness" value={restore.edge_smoothness} min={0} max={100} onChange={(value) => set("edge_smoothness", value)} onCommit={onCommit} />
      <LabeledSlider label="Color correction" value={restore.color_correction} min={0} max={100} onChange={(value) => set("color_correction", value)} onCommit={onCommit} />
      <LabeledSlider label="Sharpness" value={restore.sharpness} min={0} max={100} onChange={(value) => set("sharpness", value)} onCommit={onCommit} />
      <LabeledSlider label="Background removal" value={restore.background_refinement} min={0} max={100} onChange={(value) => set("background_refinement", value)} onCommit={onCommit} />
      <button className="text-sm underline" onClick={() => setAdvanced((open) => !open)}>
        {advanced ? "Hide advanced" : "Advanced"}
      </button>
      {advanced && (
        <div className="space-y-4">
          <LabeledSlider label="Brightness" value={restore.brightness} min={-100} max={100} onChange={(value) => set("brightness", value)} onCommit={onCommit} />
          <LabeledSlider label="Contrast" value={restore.contrast} min={-100} max={100} onChange={(value) => set("contrast", value)} onCommit={onCommit} />
          <LabeledSlider label="Saturation" value={restore.saturation} min={-100} max={100} onChange={(value) => set("saturation", value)} onCommit={onCommit} />
          <LabeledSlider label="Exposure" value={restore.exposure} min={-100} max={100} onChange={(value) => set("exposure", value)} onCommit={onCommit} />
          <LabeledSlider label="Denoise" value={restore.denoise} min={0} max={100} onChange={(value) => set("denoise", value)} onCommit={onCommit} />
          <LabeledSlider label="White balance" value={restore.white_balance} min={0} max={100} onChange={(value) => set("white_balance", value)} onCommit={onCommit} />
          <label className="flex items-center justify-between text-sm">
            Level uneven lighting
            <input
              type="checkbox"
              checked={restore.clahe}
              onChange={(event) => {
                set("clahe", event.target.checked);
                onCommit();
              }}
            />
          </label>
        </div>
      )}
      {sticker.warnings.map((warning) => (
        <p key={warning} className="text-sm text-warn">
          {warning}
        </p>
      ))}
    </div>
  );
}

function VectorPanel({
  sticker,
  onPreset,
  onControls,
}: {
  sticker: StickerItem;
  onPreset: (preset: StickerItem["vectorPreset"]) => void;
  onControls: (controls: VectorControls) => void;
}) {
  const presets: StickerItem["vectorPreset"][] = ["logo", "illustration", "detailed", "monochrome"];
  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl">Reconstruct</h2>
      <div className="grid grid-cols-2 gap-2">
        <Button size="sm" variant={sticker.mode === "faithful" ? "primary" : "secondary"} onClick={() => useProject.getState().updateSticker(sticker.id, { mode: "faithful" })}>
          Faithful
        </Button>
        <Button size="sm" variant={sticker.mode === "vector" ? "primary" : "secondary"} onClick={() => onPreset(sticker.vectorPreset)}>
          Vector
        </Button>
      </div>
      <p className="text-sm text-muted">
        Faithful keeps the cleaned photograph. Vector traces real paths with VTracer. A hybrid download is labeled as embedded raster, not as a full vector.
      </p>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <Button key={preset} size="sm" variant={sticker.vectorPreset === preset ? "primary" : "secondary"} onClick={() => onPreset(preset)}>
            {preset}
          </Button>
        ))}
      </div>
      {(
        [
          ["color_complexity", "Color complexity"],
          ["curve_smoothness", "Curve smoothness"],
          ["min_region", "Minimum region"],
          ["edge_detail", "Edge detail"],
          ["noise_filtering", "Noise filtering"],
          ["path_simplification", "Path simplification"],
        ] as const
      ).map(([key, label]) => (
        <LabeledSlider
          key={key}
          label={label}
          value={sticker.vectorControls[key]}
          min={0}
          max={100}
          onChange={(value) => useProject.getState().updateSticker(sticker.id, { vectorControls: { ...sticker.vectorControls, [key]: value }, vectorPreset: sticker.vectorPreset })}
          onCommit={() => {
            const latest = useProject.getState().stickers.find((item) => item.id === sticker.id);
            if (latest) onControls(latest.vectorControls);
          }}
        />
      ))}
      {sticker.vectorFidelity !== undefined && (
        <p className="text-sm">
          Fidelity {Math.round(sticker.vectorFidelity * 100)}% · {sticker.vectorPathCount} paths · {formatBytes(sticker.vectorBytes || 0)}
        </p>
      )}
      {sticker.vectorRecommendFaithful && (
        <p className="text-sm text-warn">Vectorization loses detail here. Faithful mode matches the photo more closely.</p>
      )}
    </div>
  );
}

function FinishPanel({
  sticker,
  onChange,
  onDownload,
}: {
  sticker: StickerItem;
  onChange: (appearance: Appearance) => void;
  onDownload: (kind: "png" | "svg" | "cut" | "zip") => void;
}) {
  const appearance = sticker.appearance;
  const occupied = occupiedSize(appearance);
  function setWidth(display: number) {
    const widthMm = toMillimetres(display, appearance.unit);
    const ratio = appearance.heightMm / Math.max(appearance.widthMm, 0.1);
    onChange({ ...appearance, widthMm, heightMm: appearance.lockAspect ? widthMm * ratio : appearance.heightMm });
  }
  function setHeight(display: number) {
    const heightMm = toMillimetres(display, appearance.unit);
    const ratio = appearance.widthMm / Math.max(appearance.heightMm, 0.1);
    onChange({ ...appearance, heightMm, widthMm: appearance.lockAspect ? heightMm * ratio : appearance.widthMm });
  }
  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl">Size and cut</h2>
      <p className="text-sm text-muted">The photograph does not know the sticker’s real size. Enter the size you want to print.</p>
      <div className="flex gap-2">
        {(["mm", "cm", "in"] as const).map((unit) => (
          <Button key={unit} size="sm" variant={appearance.unit === unit ? "primary" : "secondary"} onClick={() => onChange({ ...appearance, unit })}>
            {unit}
          </Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-sm">
          Width
          <input className="mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2" type="number" min={0.2} step={0.1} value={Number(fromMillimetres(appearance.widthMm, appearance.unit).toFixed(2))} onChange={(event) => setWidth(Number(event.target.value))} />
        </label>
        <label className="text-sm">
          Height
          <input className="mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2" type="number" min={0.2} step={0.1} value={Number(fromMillimetres(appearance.heightMm, appearance.unit).toFixed(2))} onChange={(event) => setHeight(Number(event.target.value))} />
        </label>
      </div>
      <label className="flex items-center justify-between text-sm">
        Lock aspect ratio
        <input type="checkbox" checked={appearance.lockAspect} onChange={(event) => onChange({ ...appearance, lockAspect: event.target.checked })} />
      </label>
      <p className="text-sm text-muted">
        Cut size {occupied.width.toFixed(1)} × {occupied.height.toFixed(1)} mm
        {appearance.borderEnabled ? ", including the border" : ""}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => onChange({ ...appearance, rotation: (appearance.rotation + 90) % 360 })}>
          <RotateCcw size={14} /> Rotate
        </Button>
        <Button size="sm" onClick={() => onChange({ ...appearance, flipH: !appearance.flipH })}>
          <FlipHorizontal size={14} /> Flip
        </Button>
        <Button size="sm" onClick={() => onChange({ ...appearance, flipV: !appearance.flipV })}>
          <FlipVertical size={14} /> Flip vertical
        </Button>
        <Button size="sm" onClick={() => onChange({ ...defaultAppearance(), unit: appearance.unit })}>
          Reset size
        </Button>
      </div>
      <label className="flex items-center justify-between text-sm">
        Solid background
        <input type="checkbox" checked={appearance.background === "solid"} onChange={(event) => onChange({ ...appearance, background: event.target.checked ? "solid" : "transparent" })} />
      </label>
      {appearance.background === "solid" && (
        <label className="flex items-center justify-between text-sm">
          Background color
          <input type="color" value={appearance.backgroundColor} onChange={(event) => onChange({ ...appearance, backgroundColor: event.target.value })} />
        </label>
      )}
      <label className="flex items-center justify-between text-sm">
        White border
        <input type="checkbox" checked={appearance.borderEnabled} onChange={(event) => onChange({ ...appearance, borderEnabled: event.target.checked })} />
      </label>
      {appearance.borderEnabled && (
        <>
          <LabeledSlider label="Border thickness" suffix=" mm" value={appearance.borderMm} min={0.5} max={8} step={0.5} onChange={(value) => onChange({ ...appearance, borderMm: value })} />
          <label className="flex items-center justify-between text-sm">
            Border color
            <input type="color" value={appearance.borderColor} onChange={(event) => onChange({ ...appearance, borderColor: event.target.value })} />
          </label>
        </>
      )}
      <LabeledSlider label="Cut offset" suffix=" mm" value={appearance.cutOffsetMm} min={-3} max={4} step={0.5} onChange={(value) => onChange({ ...appearance, cutOffsetMm: value })} />
      <LabeledSlider label="Simplify cut" value={appearance.cutSimplify} min={0} max={1} step={0.05} onChange={(value) => onChange({ ...appearance, cutSimplify: value })} />
      <LabeledSlider label="Smooth cut" value={appearance.cutSmooth} min={0} max={1} step={0.05} onChange={(value) => onChange({ ...appearance, cutSmooth: value })} />
      <label className="flex items-center justify-between text-sm">
        Keep interior holes
        <input type="checkbox" checked={appearance.includeHoles} onChange={(event) => onChange({ ...appearance, includeHoles: event.target.checked })} />
      </label>
      <label className="flex items-center justify-between text-sm">
        Preview cut line
        <input type="checkbox" checked={appearance.showCutPreview} onChange={(event) => onChange({ ...appearance, showCutPreview: event.target.checked })} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="primary" onClick={() => onDownload("png")}>PNG</Button>
        <Button onClick={() => onDownload("svg")}>{sticker.mode === "vector" ? "Vector SVG" : "Hybrid SVG"}</Button>
        <Button onClick={() => onDownload("cut")}>Cut SVG</Button>
        <Button onClick={() => onDownload("zip")}>ZIP</Button>
      </div>
      <p className="text-xs text-muted">
        {sticker.mode === "vector"
          ? "Vector SVG is traced geometry. Cricut will treat those paths as cuts unless you change the operation."
          : "Hybrid SVG contains the raster artwork plus a cut path. It is not a full vectorization."}{" "}
        <Link href="/guide" className="underline">
          Cricut and print notes
        </Link>
      </p>
    </div>
  );
}

function CompareView({ sticker }: { sticker: StickerItem }) {
  const [split, setSplit] = useState(50);
  if (!sticker.previewUrl) {
    return <p className="text-sm text-muted">Restore the selection to see the artwork on a checkerboard.</p>;
  }
  return (
    <div>
      <div className="relative overflow-hidden rounded-3xl border border-line">
        <img src={apiUrl(sticker.beforeUrl || sticker.previewUrl)} alt="" className="block w-full" />
        <div className="checker absolute inset-0" style={{ clipPath: `inset(0 0 0 ${split}%)` }}>
          <img src={apiUrl(sticker.previewUrl)} alt="Restored sticker" className="h-full w-full object-contain" />
        </div>
      </div>
      <label className="mt-3 block text-sm">
        Before and after
        <input className="mt-1 w-full" type="range" min={0} max={100} value={split} onChange={(event) => setSplit(Number(event.target.value))} />
      </label>
    </div>
  );
}

function CompareVector({ sticker }: { sticker: StickerItem }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <figure className="checker overflow-hidden rounded-3xl border border-line">
        {sticker.previewUrl && <img src={apiUrl(sticker.previewUrl)} alt="Faithful artwork" className="w-full" />}
        <figcaption className="bg-elev px-3 py-2 text-xs">Faithful raster</figcaption>
      </figure>
      <figure className="checker overflow-hidden rounded-3xl border border-line">
        {sticker.vectorPreviewUrl ? (
          <img src={apiUrl(sticker.vectorPreviewUrl)} alt="Vector reconstruction" className="w-full" />
        ) : (
          <p className="p-6 text-sm">Choose Vector to trace paths.</p>
        )}
        <figcaption className="bg-elev px-3 py-2 text-xs">Vector paths</figcaption>
      </figure>
    </div>
  );
}

function FinishPreview({ sticker, cutPath }: { sticker: StickerItem; cutPath: string }) {
  const view = sticker.cutlineView || { width: sticker.pixelWidth || 1, height: sticker.pixelHeight || 1 };
  return (
    <div className="checker relative overflow-hidden rounded-3xl border border-line">
      {sticker.previewUrl && (
        <img
          src={apiUrl(sticker.previewUrl)}
          alt="Sticker ready to size"
          className="w-full"
          style={{
            transform: `rotate(${sticker.appearance.rotation}deg) scaleX(${sticker.appearance.flipH ? -1 : 1}) scaleY(${sticker.appearance.flipV ? -1 : 1})`,
          }}
        />
      )}
      {sticker.appearance.showCutPreview && cutPath && (
        <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${view.width} ${view.height}`} preserveAspectRatio="xMidYMid meet">
          <path d={cutPath} fill="none" stroke="#e23b2b" strokeWidth={Math.max(view.width, view.height) * 0.004} />
        </svg>
      )}
    </div>
  );
}

function SheetSettings() {
  const project = useProject();
  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl">Sheet</h2>
      <div className="flex gap-2">
        <Button size="sm" variant={project.page === "letter" ? "primary" : "secondary"} onClick={() => project.setPage("letter")}>Letter</Button>
        <Button size="sm" variant={project.page === "a4" ? "primary" : "secondary"} onClick={() => project.setPage("a4")}>A4</Button>
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant={project.orientation === "portrait" ? "primary" : "secondary"} onClick={() => project.setOrientation("portrait")}>Portrait</Button>
        <Button size="sm" variant={project.orientation === "landscape" ? "primary" : "secondary"} onClick={() => project.setOrientation("landscape")}>Landscape</Button>
      </div>
      <LabeledSlider label="Margin" suffix=" mm" value={project.marginMm} min={8} max={25} onChange={project.setMargin} />
      <LabeledSlider label="Spacing" suffix=" mm" value={project.spacingMm} min={0} max={15} onChange={project.setSpacing} />
      <label className="flex items-center justify-between text-sm">
        10 mm calibration square
        <input type="checkbox" checked={project.calibration} onChange={(event) => project.setCalibration(event.target.checked)} />
      </label>
      <label className="flex items-center justify-between text-sm">
        Cutting guides
        <input type="checkbox" checked={project.guides} onChange={(event) => project.setGuides(event.target.checked)} />
      </label>
      <p className="text-sm text-muted">Print at 100% or Actual Size. Fit to Page will shrink the stickers.</p>
    </div>
  );
}

function SheetEditor({
  setBusy,
  setError,
}: {
  setBusy: (value: string | null) => void;
  setError: (value: string | null) => void;
}) {
  const project = useProject();
  const page = pageSizeMm(project.page, project.orientation);
  const ready = project.stickers.filter((sticker) => sticker.artifactId);

  function add(sticker: StickerItem) {
    project.setSheet([
      ...project.sheet,
      { key: `${sticker.id}-${project.sheet.length}-${Date.now()}`, stickerId: sticker.id, xMm: project.marginMm, yMm: project.marginMm, rotation: 0 },
    ]);
  }

  async function arrange() {
    if (!project.sheet.length) {
      setError("Add a restored sticker to the sheet first.");
      return;
    }
    setError(null);
    setBusy("Preparing export");
    try {
      const result = await layoutSheet(sheetBody(true));
      const byId = new Map(result.items.map((item) => [item.id, item]));
      project.setSheet(
        project.sheet.map((item) => {
          const placed = byId.get(item.key);
          return placed ? { ...item, xMm: placed.x_mm, yMm: placed.y_mm } : item;
        }),
      );
      if (result.overflows.length) setError("Some stickers do not fit. Make them smaller or use another page.");
      project.setWarnings(result.warnings);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not arrange the sheet.");
    } finally {
      setBusy(null);
    }
  }

  async function download() {
    if (!project.sheet.length) return;
    setError(null);
    setBusy("Preparing export");
    try {
      const result = await exportSheet(sheetBody(false));
      if (result.download_url && result.filename) await downloadFile(result.download_url, result.filename);
      project.setWarnings(result.warnings || []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The PDF could not be created.");
    } finally {
      setBusy(null);
    }
  }

  function sheetBody(auto: boolean) {
    return {
      page: project.page,
      orientation: project.orientation,
      margin_mm: project.calibration ? Math.max(project.marginMm, 14) : project.marginMm,
      spacing_mm: project.spacingMm,
      calibration_square: project.calibration,
      show_guides: project.guides,
      auto_pack: auto,
      allow_overlap: false,
      items: project.sheet.map((item) => {
        const sticker = project.stickers.find((entry) => entry.id === item.stickerId);
        return {
          id: item.key,
          artifact_id: sticker?.artifactId,
          x_mm: item.xMm,
          y_mm: item.yMm,
          rotation_deg: item.rotation,
          appearance: sticker ? appearancePayload(sticker.appearance) : appearancePayload(defaultAppearance()),
        };
      }),
    };
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {ready.map((sticker) => (
          <Button key={sticker.id} size="sm" onClick={() => add(sticker)}>
            Add {sticker.name}
          </Button>
        ))}
        <Button size="sm" variant="primary" onClick={() => void arrange()}>
          Arrange
        </Button>
        <Button size="sm" onClick={() => void download()}>
          Download PDF
        </Button>
      </div>
      <div className="mx-auto w-full max-w-sm rounded-2xl border border-line bg-white p-3 shadow-card lg:max-w-3xl" style={{ aspectRatio: `${page.width} / ${page.height}` }}>
        <div className="relative h-full w-full">
          {project.sheet.map((item) => {
            const sticker = project.stickers.find((entry) => entry.id === item.stickerId);
            if (!sticker) return null;
            const size = occupiedSize(sticker.appearance);
            return (
              <div
                key={item.key}
                className="absolute cursor-grab overflow-hidden border border-dashed border-ink/30"
                style={{
                  left: `${(item.xMm / page.width) * 100}%`,
                  top: `${(item.yMm / page.height) * 100}%`,
                  width: `${(size.width / page.width) * 100}%`,
                  height: `${(size.height / page.height) * 100}%`,
                }}
                onPointerDown={(event) => {
                  const node = event.currentTarget.parentElement;
                  if (!node) return;
                  const bounds = node.getBoundingClientRect();
                  const startX = event.clientX;
                  const startY = event.clientY;
                  const originX = item.xMm;
                  const originY = item.yMm;
                  function move(moveEvent: PointerEvent) {
                    const dx = ((moveEvent.clientX - startX) / bounds.width) * page.width;
                    const dy = ((moveEvent.clientY - startY) / bounds.height) * page.height;
                    project.updateSheetItem(item.key, { xMm: Math.max(0, originX + dx), yMm: Math.max(0, originY + dy) });
                  }
                  function up() {
                    window.removeEventListener("pointermove", move);
                    window.removeEventListener("pointerup", up);
                  }
                  window.addEventListener("pointermove", move);
                  window.addEventListener("pointerup", up);
                }}
              >
                {sticker.previewUrl && (
                  <img src={apiUrl(sticker.previewUrl)} alt={sticker.name} className="h-full w-full object-contain" draggable={false} />
                )}
              </div>
            );
          })}
        </div>
      </div>
      <ul className="mt-3 space-y-2 text-sm">
        {project.sheet.map((item) => {
          const sticker = project.stickers.find((entry) => entry.id === item.stickerId);
          return (
            <li key={item.key} className="flex flex-wrap items-center gap-2">
              <span>{sticker?.name}</span>
              <Button size="sm" onClick={() => project.updateSheetItem(item.key, { rotation: item.rotation + 15 })}>
                Rotate 15°
              </Button>
              <Button
                size="sm"
                onClick={() =>
                  project.setSheet([
                    ...project.sheet,
                    { ...item, key: `${item.key}-copy-${Date.now()}`, xMm: item.xMm + 8, yMm: item.yMm + 8 },
                  ])
                }
              >
                Duplicate
              </Button>
              <Button size="sm" onClick={() => project.setSheet(project.sheet.filter((entry) => entry.key !== item.key))}>
                Remove
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

