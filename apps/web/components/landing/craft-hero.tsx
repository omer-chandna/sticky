import { UploadSimple } from "@phosphor-icons/react/dist/ssr";

import { CraftKnife, Pencil, SteelRuler } from "@/components/landing/craft-tools";
import { BadgeSticker, CloudSticker, HelloSticker, LabelSticker, StarSticker } from "@/components/landing/sticker-art";

type Vars = React.CSSProperties & Record<`--${string}`, string>;

/**
 * The hero is a cutting mat seen from above: a sheet with the restored sticker being cut out,
 * a craft knife, a steel rule, a pencil, and stickers already cut and peeled.
 */
export function CraftHero({ onPick, onExample, loading }: { onPick: () => void; onExample: () => void; loading: boolean }) {
  return (
    <section className="p-2" aria-labelledby="hero-heading">
      <div className="cutting-mat relative flex min-h-[calc(100svh-1rem)] items-center overflow-hidden rounded-3xl text-cream">
        <MatMarkings />

        <div className="relative mx-auto grid w-full max-w-6xl items-center gap-12 px-6 pb-16 pt-32 lg:grid-cols-[0.85fr_1.15fr] lg:pb-16 lg:pt-24">
          <div className="relative z-10 text-center lg:text-left">
            <p
              className="caption-4 inline-flex items-center gap-2 rounded-full border px-3 py-2 text-foam"
              style={{ borderColor: "rgba(244,239,226,0.22)", backgroundColor: "rgba(38,51,15,0.7)" }}
            >
              <span className="h-2 w-2 rounded-full bg-matcha" /> Open source · runs locally
            </p>
            <h1 id="hero-heading" className="display-1 hero-cream mx-auto mt-6 max-w-[680px] lg:mx-0">
              Your stickers,
              <br />
              wherever
              <br />
              you go.
            </h1>
            <p className="lead mx-auto mt-6 max-w-[680px] opacity-80 lg:mx-0 lg:max-w-md">
              Your photos and messages move to every new device. Your stickers hold memories too: the gig, the trip, the friend who handed you one. Photograph them, and Sticky gives you files to print and stick on the next one.
            </p>
            <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start">
              <button
                type="button"
                onClick={onPick}
                className="button-md inline-flex items-center gap-2 rounded-full bg-foam px-6 py-3 text-matcha-deep transition-[transform,background-color] duration-300 ease-base hover:-translate-y-0.5 hover:bg-cream active:scale-[0.98]"
              >
                <UploadSimple size={18} weight="bold" aria-hidden /> Restore a sticker
              </button>
              <button
                type="button"
                onClick={onExample}
                className="button-md rounded-full px-3 py-2 text-cream underline decoration-2 underline-offset-8 transition-opacity duration-300 ease-base hover:opacity-80"
                style={{ textDecorationColor: "rgba(201,217,142,0.5)" }}
              >
                {loading ? "Loading the example…" : "or try an example"}
              </button>
            </div>
            <p className="caption-5 mt-6 opacity-60">No account · No API key · Exports aim for 300 DPI</p>
          </div>

          <Desk />
        </div>
      </div>
    </section>
  );
}

function Desk() {
  return (
    <div className="relative mx-auto aspect-[10/9] w-full max-w-2xl" role="img" aria-label="A sticker sheet on a cutting mat with a craft knife, a steel ruler, a pencil, and cut out stickers">
      {/* Sticker sheet with the restored artwork, cut line drawing around it */}
      <div className="stick absolute left-[4%] top-[10%] w-[62%]" style={{ "--r": "-4deg", "--r-from": "-10deg", "--d": "150ms" } as Vars}>
        <div className="on-desk relative aspect-[5/4] rounded-sm bg-[#fbf8f0]">
          <BadgeSticker cut={false} className="absolute left-[12%] top-[10%] w-[52%]" />
          <StarSticker cut={false} className="absolute right-[7%] top-[12%] w-[20%] rotate-12" />
          <svg viewBox="0 0 100 80" className="absolute inset-0 h-full w-full" aria-hidden>
            {/* Where a round sticker was peeled off: the empty backing keeps its outline */}
            <circle cx="83" cy="55" r="10" fill="#efe9d8" stroke="#5c7f23" strokeWidth="0.4" strokeDasharray="1.2 1.2" />
            <circle cx="38" cy="34" r="28" fill="none" stroke="#5c7f23" strokeWidth="0.5" strokeDasharray="1.6 1.6" opacity="0.7" />
            <circle
              cx="38"
              cy="34"
              r="28"
              pathLength={100}
              fill="none"
              stroke="#26330f"
              strokeWidth="0.7"
              className="cut-line"
              transform="rotate(-90 38 34)"
              style={{ "--len": "100" } as Vars}
            />
          </svg>
          <span className="absolute bottom-[3%] left-[4%] hidden font-mono text-xs sm:block text-[#5e6a4e]">Ø 60 mm</span>
        </div>
      </div>

      {/* Knife resting with its blade at the sheet's corner */}
      <div className="absolute left-[50%] top-[-4%] w-[58%]">
        <div className="knife-in on-desk" style={{ "--r": "158deg" } as Vars}>
          <CraftKnife className="w-full" />
        </div>
      </div>

      {/* Cut stickers */}
      <Loose className="right-[3%] top-[33%] w-[24%]" r="-8deg" d="700ms">
        <HelloSticker className="w-full" />
      </Loose>
      <Loose className="bottom-[1%] left-[44%] w-[18%]" r="10deg" d="850ms">
        <CloudSticker className="w-full" />
      </Loose>
      <PeeledSticker />

      {/* Steel rule across the mat, and a pencil */}
      <div className="stick absolute bottom-[25%] left-[-8%] w-[92%]" style={{ "--r": "-6deg", "--r-from": "-2deg", "--d": "350ms" } as Vars}>
        <SteelRuler className="on-desk w-full" />
      </div>
      <div className="stick absolute bottom-[4%] left-[0%] w-[44%]" style={{ "--r": "-14deg", "--r-from": "-24deg", "--d": "1100ms" } as Vars}>
        <Pencil className="on-desk w-full" />
      </div>
    </div>
  );
}

function Loose({ className, r, d, children }: { className: string; r: string; d: string; children: React.ReactNode }) {
  return (
    <div className={`stick absolute ${className}`} style={{ "--r": r, "--r-from": "0deg", "--d": d } as Vars}>
      <div className="lift" style={{ "--r": "0deg" } as Vars}>
        {children}
      </div>
    </div>
  );
}

/** The label sticker, its top corner lifted off the backing. */
function PeeledSticker() {
  return (
    <div className="stick absolute bottom-[1%] right-[2%] w-[25%]" style={{ "--r": "-6deg", "--r-from": "6deg", "--d": "1000ms" } as Vars}>
      <div className="lift relative" style={{ "--r": "0deg" } as Vars}>
        <div style={{ clipPath: "polygon(-10% -10%, 60% -10%, 110% 40%, 110% 110%, -10% 110%)" }}>
          <LabelSticker className="block w-full" />
        </div>
        <span
          aria-hidden
          className="absolute right-0 top-0 h-[30%] w-[30%]"
          style={{
            clipPath: "polygon(0 0, 100% 100%, 0 100%)",
            background: "linear-gradient(225deg, #d9d4c4, #ffffff 60%)",
            filter: "drop-shadow(-3px 4px 4px rgba(8,12,2,0.35))",
          }}
        />
      </div>
    </div>
  );
}

/** Edge numbers and an angle guide, printed on the mat like a real one. */
function MatMarkings() {
  const top = Array.from({ length: 16 }, (_, i) => i + 1);
  const side = Array.from({ length: 9 }, (_, i) => i + 1);
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 font-mono text-xs text-foam" style={{ opacity: 0.5 }}>
      {top.map((n) => (
        <span key={`t${n}`} className="absolute top-2" style={{ left: n * 120 + 4 }}>
          {n * 5}
        </span>
      ))}
      {side.map((n) => (
        <span key={`s${n}`} className="absolute left-2" style={{ top: n * 120 + 4 }}>
          {n * 5}
        </span>
      ))}
      <span className="absolute bottom-0 left-0 h-px w-[160%] origin-bottom-left -rotate-45" style={{ backgroundColor: "rgba(201,217,142,0.35)" }} />
      <span className="absolute bottom-6 left-28">45°</span>
    </div>
  );
}
