"use client";

import { useState } from "react";

export function BeforeAfter({ before, after, alt }: { before: string; after: string; alt: string }) {
  const [position, setPosition] = useState(62);
  return (
    <div className="relative overflow-hidden rounded-3xl border border-line bg-elev shadow-card">
      <img src={before} alt="" className="block h-auto w-full" />
      <div className="checker absolute inset-0" style={{ clipPath: `inset(0 0 0 ${position}%)` }}>
        <img src={after} alt={alt} className="h-full w-full object-cover" />
      </div>
      <div className="pointer-events-none absolute inset-y-0" style={{ left: `${position}%` }}>
        <div className="h-full w-px bg-white shadow" />
      </div>
      <div className="absolute left-3 top-3 rounded-full bg-elev/90 px-2 py-1 text-xs">Photo</div>
      <div className="absolute right-3 top-3 rounded-full bg-elev/90 px-2 py-1 text-xs">Restored</div>
      <label className="absolute inset-x-4 bottom-4">
        <span className="sr-only">Compare the photograph and the restored sticker</span>
        <input
          type="range"
          min={5}
          max={95}
          value={position}
          onChange={(event) => setPosition(Number(event.target.value))}
          className="w-full"
        />
      </label>
    </div>
  );
}
