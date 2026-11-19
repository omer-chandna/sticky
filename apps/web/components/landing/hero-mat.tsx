import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

/** A cutting mat with the photographed sticker on one side and the restored cut out on the other. */
export function HeroMat() {
  return (
    <div className="relative mx-auto max-w-5xl">
      <div className="relative overflow-hidden rounded-3xl border border-line p-6 sm:p-12" style={{ backgroundColor: "color-mix(in srgb, var(--elev) 55%, transparent)" }}>
        <Ruler />
        <div className="relative grid items-center gap-8 pt-6 sm:grid-cols-[1fr_auto_1fr] sm:gap-6">
          <figure className="stick mx-auto w-full max-w-sm" style={{ "--r": "-4deg", "--r-from": "-10deg", "--d": "150ms" } as React.CSSProperties}>
            <div className="rounded-2xl border border-line bg-elev p-2 shadow-card">
              <img
                src="/demo/before-matcha.png"
                alt="A photograph of a green sticker, tilted on a grey laptop lid"
                width={1200}
                height={900}
                className="block h-auto w-full rounded-lg"
              />
            </div>
            <figcaption className="caption-4 mt-4 text-center text-muted">Your photo</figcaption>
          </figure>

          <div className="flex justify-center" aria-hidden>
            <span className="stick flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-ink sm:rotate-0" style={{ "--d": "450ms" } as React.CSSProperties}>
              <ArrowRight size={20} weight="bold" className="rotate-90 sm:rotate-0" />
            </span>
          </div>

          <figure className="stick relative mx-auto w-full max-w-sm" style={{ "--r": "3deg", "--r-from": "12deg", "--d": "650ms" } as React.CSSProperties}>
            <div className="checker relative rounded-2xl border border-dashed border-muted p-6">
              <img
                src="/demo/restored-matcha.png"
                alt="The same sticker, straightened, with the background removed"
                width={594}
                height={475}
                className="die-cut block h-auto w-full rounded-sm"
              />
              <span className="caption-4 absolute -bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-ink px-2 py-1 text-bg">Cut line</span>
            </div>
            <figcaption className="caption-4 mt-6 text-center text-muted">Ready to print</figcaption>
          </figure>
        </div>

      </div>
    </div>
  );
}


function Ruler() {
  const ticks = Array.from({ length: 61 }, (_, i) => i);
  return (
    <div aria-hidden className="absolute inset-x-6 top-4 flex items-start justify-between sm:inset-x-12">
      {ticks.map((i) => (
        <span key={i} className="relative flex flex-col items-center">
          <span className={`w-px bg-muted ${i % 10 === 0 ? "h-3" : i % 5 === 0 ? "h-2" : "h-1"} ${i % 2 && i % 5 ? "hidden sm:block" : ""}`} />
          {i % 10 === 0 && <span className="absolute top-4 font-mono text-xs text-muted">{i}</span>}
        </span>
      ))}
    </div>
  );
}
