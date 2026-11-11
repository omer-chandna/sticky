"use client";

import type { Point } from "@sticky/shared";
import { useEffect, useRef, useState } from "react";

import type { StickerItem, Tool } from "@/lib/store";

function clamp(value: number) {
  return Math.min(1, Math.max(0, value));
}

function insidePolygon(point: Point, polygon: Point[]) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i];
    const b = polygon[j];
    const intersect = a.y > point.y !== b.y > point.y && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y + 1e-9) + a.x;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function SelectionCanvas({
  src,
  stickers,
  activeId,
  selectedIds,
  tool,
  onToggle,
  onChangePolygon,
  onChangeQuad,
  onBrush,
}: {
  src: string;
  stickers: StickerItem[];
  activeId: string | null;
  selectedIds: string[];
  tool: Tool;
  onToggle: (id: string) => void;
  onChangePolygon: (id: string, polygon: Point[]) => void;
  onChangeQuad: (id: string, quad: Point[]) => void;
  onBrush: (dataUrl: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const maskRef = useRef<HTMLCanvasElement>(null);
  const viewRef = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ kind: string; index?: number; origin?: Point; start?: Point[]; pointer?: Point } | null>(null);
  const [draftRect, setDraftRect] = useState<Point[] | null>(null);
  const active = stickers.find((sticker) => sticker.id === activeId) ?? null;

  useEffect(() => {
    const image = new Image();
    image.onload = () => {
      const mask = maskRef.current;
      const view = viewRef.current;
      if (!mask || !view) return;
      const width = Math.min(image.naturalWidth || 1000, 1100);
      const height = Math.round(width * ((image.naturalHeight || 1) / (image.naturalWidth || 1)));
      mask.width = width;
      mask.height = height;
      view.width = width;
      view.height = height;
      const context = mask.getContext("2d");
      if (!context) return;
      context.clearRect(0, 0, width, height);
      if (active?.brushDataUrl) {
        const existing = new Image();
        existing.onload = () => {
          context.drawImage(existing, 0, 0, width, height);
          paintView();
        };
        existing.src = active.brushDataUrl;
      } else if ((tool === "brush" || tool === "erase") && active && active.polygon.length >= 3) {
        context.fillStyle = "#ffffff";
        context.beginPath();
        active.polygon.forEach((point, index) => {
          const x = point.x * width;
          const y = point.y * height;
          if (index === 0) context.moveTo(x, y);
          else context.lineTo(x, y);
        });
        context.closePath();
        context.fill();
        paintView();
      } else {
        paintView();
      }
    };
    image.src = src;
  }, [src, active?.id, active?.brushDataUrl, tool]);

  function paintView() {
    const mask = maskRef.current;
    const view = viewRef.current;
    if (!mask || !view) return;
    const context = view.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, view.width, view.height);
    context.drawImage(mask, 0, 0);
    context.globalCompositeOperation = "source-in";
    context.fillStyle = "rgba(226, 59, 43, 0.45)";
    context.fillRect(0, 0, view.width, view.height);
    context.globalCompositeOperation = "source-over";
  }

  function eventPoint(event: React.PointerEvent): Point {
    const bounds = (wrapRef.current ?? event.currentTarget).getBoundingClientRect();
    return {
      x: clamp((event.clientX - bounds.left) / bounds.width),
      y: clamp((event.clientY - bounds.top) / bounds.height),
    };
  }

  function paintBrush(point: Point, erase: boolean) {
    const mask = maskRef.current;
    if (!mask) return;
    const context = mask.getContext("2d");
    if (!context) return;
    const radius = Math.max(8, mask.width * 0.02);
    context.beginPath();
    context.arc(point.x * mask.width, point.y * mask.height, radius, 0, Math.PI * 2);
    if (erase) {
      context.globalCompositeOperation = "destination-out";
      context.fill();
      context.globalCompositeOperation = "source-over";
    } else {
      context.fillStyle = "#ffffff";
      context.fill();
    }
    paintView();
  }

  function onPointerDown(event: React.PointerEvent) {
    const point = eventPoint(event);
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    if (tool === "brush" || tool === "erase") {
      drag.current = { kind: "brush" };
      paintBrush(point, tool === "erase");
      return;
    }
    if (tool === "rect") {
      drag.current = { kind: "rect", pointer: point };
      setDraftRect([point, point]);
      return;
    }
    if (tool === "polygon" && active) {
      const polygon = active.polygon;
      if (polygon.length >= 3 && Math.hypot(point.x - polygon[0].x, point.y - polygon[0].y) < 0.03) {
        return;
      }
      onChangePolygon(active.id, [...polygon, point]);
      return;
    }
    if (!active) return;
    if (tool === "quad" && active.quad) {
      const index = active.quad.findIndex((corner) => Math.hypot(corner.x - point.x, corner.y - point.y) < 0.04);
      if (index >= 0) drag.current = { kind: "quad", index };
      return;
    }
    const handle = active.polygon.findIndex((corner) => Math.hypot(corner.x - point.x, corner.y - point.y) < 0.035);
    if (handle >= 0) {
      drag.current = { kind: "handle", index: handle };
      return;
    }
    if (tool === "select" && active.polygon.length >= 3 && insidePolygon(point, active.polygon)) {
      drag.current = { kind: "move", origin: point, start: active.polygon };
    }
  }

  function onPointerMove(event: React.PointerEvent) {
    if (!drag.current) return;
    const point = eventPoint(event);
    if (drag.current.kind === "brush") {
      paintBrush(point, tool === "erase");
      return;
    }
    if (drag.current.kind === "rect" && drag.current.pointer) {
      setDraftRect([drag.current.pointer, point]);
      return;
    }
    if (!active) return;
    if (drag.current.kind === "quad" && active.quad && drag.current.index !== undefined) {
      const quad = active.quad.map((corner, index) => (index === drag.current?.index ? point : corner));
      onChangeQuad(active.id, quad);
      return;
    }
    if (drag.current.kind === "handle" && drag.current.index !== undefined) {
      const polygon = active.polygon.map((corner, index) => (index === drag.current?.index ? point : corner));
      onChangePolygon(active.id, polygon);
      return;
    }
    if (drag.current.kind === "move" && drag.current.origin && drag.current.start) {
      const dx = point.x - drag.current.origin.x;
      const dy = point.y - drag.current.origin.y;
      onChangePolygon(
        active.id,
        drag.current.start.map((corner) => ({ x: clamp(corner.x + dx), y: clamp(corner.y + dy) })),
      );
    }
  }

  function onPointerUp() {
    if (drag.current?.kind === "rect" && draftRect && active) {
      const [a, b] = draftRect;
      onChangePolygon(active.id, [
        { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y) },
        { x: Math.max(a.x, b.x), y: Math.min(a.y, b.y) },
        { x: Math.max(a.x, b.x), y: Math.max(a.y, b.y) },
        { x: Math.min(a.x, b.x), y: Math.max(a.y, b.y) },
      ]);
      setDraftRect(null);
    }
    if (drag.current?.kind === "brush") {
      const url = maskRef.current?.toDataURL("image/png");
      if (url) onBrush(url);
    }
    drag.current = null;
  }

  const rectPreview = draftRect
    ? [
        { x: Math.min(draftRect[0].x, draftRect[1].x), y: Math.min(draftRect[0].y, draftRect[1].y) },
        { x: Math.max(draftRect[0].x, draftRect[1].x), y: Math.min(draftRect[0].y, draftRect[1].y) },
        { x: Math.max(draftRect[0].x, draftRect[1].x), y: Math.max(draftRect[0].y, draftRect[1].y) },
        { x: Math.min(draftRect[0].x, draftRect[1].x), y: Math.max(draftRect[0].y, draftRect[1].y) },
      ]
    : null;

  return (
    <div ref={wrapRef} className="relative w-full touch-none select-none" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
      <img src={src} alt="Uploaded sticker photograph" className="block h-auto w-full" draggable={false} />
      <canvas ref={viewRef} className="pointer-events-none absolute inset-0 h-full w-full" />
      <canvas ref={maskRef} className="hidden" />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
        {stickers.map((sticker) => {
          const activeShape = sticker.id === activeId;
          const chosen = selectedIds.includes(sticker.id);
          const points = sticker.polygon.map((point) => `${point.x},${point.y}`).join(" ");
          return (
            <polygon
              key={sticker.id}
              points={points}
              fill={chosen ? "rgba(226,59,43,0.16)" : "transparent"}
              stroke={activeShape ? "#e23b2b" : "#1d1916"}
              strokeWidth={activeShape ? 0.006 : 0.003}
              vectorEffect="non-scaling-stroke"
              onClick={(event) => {
                event.stopPropagation();
                if (tool === "select") onToggle(sticker.id);
              }}
            />
          );
        })}
        {rectPreview && (
          <polygon points={rectPreview.map((point) => `${point.x},${point.y}`).join(" ")} fill="rgba(226,59,43,0.15)" stroke="#e23b2b" strokeWidth="0.004" />
        )}
        {active?.usePerspective && active.quad && (
          <polygon points={active.quad.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke="#1d7a58" strokeWidth="0.004" strokeDasharray="0.012 0.008" />
        )}
        {(tool === "quad" ? active?.quad : active?.polygon)?.map((point, index) => (
          <circle key={index} cx={point.x} cy={point.y} r="0.012" fill="#fffcf8" stroke="#1d1916" strokeWidth="0.003" />
        ))}
      </svg>
    </div>
  );
}
