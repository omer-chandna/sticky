import { ArrowLeft, Printer, Scissors, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import type { Metadata } from "next";
import Link from "next/link";

import { SteelRuler } from "@/components/landing/craft-tools";
import { SiteNav } from "@/components/landing/site-nav";
import { StarSticker } from "@/components/landing/sticker-art";
import { Wordmark } from "@/components/wordmark";

export const metadata: Metadata = {
  title: "Print and cut guide, Sticky",
  description: "How to print Sticky files at true size on sticker paper, and how to use them with Cricut Design Space.",
};

const STEPS = [
  "Download the sheet PDF.",
  "In the print dialog, choose 100% or Actual Size. Do not choose Fit to Page.",
  "Load sticker paper that matches the page, Letter or A4.",
  "Optional: print the 10 mm calibration square first. If it does not measure 10 mm, the printer is scaling the page.",
];

export default function GuidePage() {
  return (
    <div className="dot-grid min-h-screen">
      <a
        href="#main"
        className="button-sm fixed left-4 top-4 z-50 -translate-y-24 rounded-full bg-ink px-3 py-2 text-bg transition-transform duration-300 ease-base focus:translate-y-0"
      >
        Skip to content
      </a>
      <SiteNav current="/guide" />

      <header className="p-2">
        <div className="cutting-mat relative overflow-hidden rounded-3xl px-6 pb-16 pt-32 text-cream sm:pb-24 sm:pt-40">
          <div className="relative z-10 mx-auto max-w-3xl">
            <Link href="/" className="caption-4 inline-flex items-center gap-2 text-foam transition-opacity duration-300 ease-base hover:opacity-80">
              <ArrowLeft size={14} weight="bold" aria-hidden /> Back to Sticky
            </Link>
            <h1 className="heading-2 hero-cream mt-6 sm:text-6xl">Print and cut</h1>
            <p className="lead mt-4 max-w-xl opacity-80">
              Sticky prepares files. It does not talk to a Cricut machine, and it does not draw Cricut’s registration marks.
            </p>
          </div>
          <SteelRuler className="on-desk absolute -bottom-3 right-[-6%] hidden w-[52%] -rotate-3 md:block" />
          <StarSticker className="absolute right-[12%] top-28 hidden w-16 rotate-12 md:block" />
        </div>
      </header>

      <main id="main" className="mx-auto grid max-w-3xl gap-4 px-4 py-16 sm:py-24">
        <section className="rounded-3xl border border-line bg-elev p-8" aria-labelledby="print-heading">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-foam text-[#26330f]">
            <Printer size={24} weight="bold" aria-hidden />
          </span>
          <h2 id="print-heading" className="heading-5 mt-6">
            Printing on sticker paper
          </h2>
          <ol className="mt-6 flex flex-col gap-4">
            {STEPS.map((step, i) => (
              <li key={step} className="flex gap-4">
                <span className="font-mono text-sm font-medium text-accent">0{i + 1}</span>
                <span className="body-3">{step}</span>
              </li>
            ))}
          </ol>
          <p className="body-6 mt-6 rounded-2xl bg-bg p-4 text-muted">
            Exports aim for 300 DPI at the size you entered. Enlarging a small photo does not add detail that was not in the picture.
          </p>
        </section>

        <section className="rounded-3xl border border-line bg-elev p-8" aria-labelledby="cricut-heading">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-pop text-[#3a2a08]">
            <Scissors size={24} weight="bold" aria-hidden />
          </span>
          <h2 id="cricut-heading" className="heading-5 mt-6">
            Cricut Design Space
          </h2>
          <div className="body-3 mt-4 flex flex-col gap-4">
            <p>
              For a detailed color sticker, use Print Then Cut. Import the transparent PNG (or the hybrid SVG’s raster artwork), set the size to the millimetres shown in Sticky, and use Design Space’s own print and cut flow. Do not expect a Sticky PDF to contain Cricut’s optical registration marks.
            </p>
            <p>
              Design Space imports SVG paths as cut geometry unless you change the operation. The separate cut SVG is only the outer silhouette. The vector SVG is real path artwork, which is useful for simple logos and will be cut as those paths if you leave the operation on Cut. Maximum cut size depends on your machine and your print settings. Sticky does not assume one limit for every machine.
            </p>
            <p className="text-muted">A hybrid SVG is labeled in the file as embedded raster artwork plus a cut outline. It is not a fully vectorized sticker.</p>
          </div>
        </section>

        <section className="cutting-mat rounded-3xl p-8 text-cream" aria-labelledby="limits-heading">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-clay text-cream">
            <WarningCircle size={24} weight="bold" aria-hidden />
          </span>
          <h2 id="limits-heading" className="heading-5 mt-6">
            When the photo is not enough
          </h2>
          <p className="body-3 mt-4 opacity-80">
            Glare, blur, and missing pieces stay missing. Sticky will say so instead of redrawing the artwork. Take another photo facing the sticker, with even light, and run it again. The first photo remains available until you remove it or the temporary files expire.
          </p>
        </section>

        <div className="mt-8 flex flex-col items-center gap-4 text-center">
          <p className="body-3 text-muted">Ready to bring a sticker over?</p>
          <Link
            href="/"
            className="button-md inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3 text-accent-ink transition-transform duration-300 ease-base hover:-translate-y-0.5 active:scale-[0.98]"
          >
            Restore a sticker
          </Link>
        </div>
      </main>

      <footer className="mx-auto flex max-w-3xl flex-col gap-4 px-4 pb-12 sm:flex-row sm:items-center sm:justify-between">
        <Wordmark className="text-xl" />
        <a href="https://github.com/omer-chandna/sticky" className="body-6 text-muted hover:text-ink">
          Source on GitHub
        </a>
      </footer>
    </div>
  );
}
