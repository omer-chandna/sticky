import Link from "next/link";

import { Wordmark } from "@/components/wordmark";

export default function GuidePage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-8">
      <Link href="/" className="inline-block">
        <Wordmark />
      </Link>
      <h1 className="mt-8 font-display text-4xl">Print and cut</h1>
      <p className="mt-3 text-muted">
        Sticky prepares files. It does not talk to a Cricut machine, and it does not draw Cricut’s registration marks.
      </p>

      <section className="mt-8 space-y-3">
        <h2 className="font-display text-2xl">Printing on sticker paper</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm leading-6">
          <li>Download the sheet PDF.</li>
          <li>In the print dialog, choose 100% or Actual Size. Do not choose Fit to Page.</li>
          <li>Load sticker paper that matches the page, Letter or A4.</li>
          <li>Optional: print the 10 mm calibration square first. If it does not measure 10 mm, the printer is scaling the page.</li>
        </ol>
        <p className="text-sm text-muted">
          Exports aim for 300 DPI at the size you entered. Enlarging a small photo does not add detail that was not in the picture.
        </p>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="font-display text-2xl">Cricut Design Space</h2>
        <p className="text-sm leading-6">
          For a detailed color sticker, use Print Then Cut. Import the transparent PNG (or the hybrid SVG’s raster artwork), set the size to the millimetres shown in Sticky, and use Design Space’s own print and cut flow. Do not expect a Sticky PDF to contain Cricut’s optical registration marks.
        </p>
        <p className="text-sm leading-6">
          Design Space imports SVG paths as cut geometry unless you change the operation. The separate cut SVG is only the outer silhouette. The vector SVG is real path artwork, which is useful for simple logos and will be cut as those paths if you leave the operation on Cut. Maximum cut size depends on your machine and your print settings. Sticky does not assume one limit for every machine.
        </p>
        <p className="text-sm leading-6">
          A hybrid SVG is labeled in the file as embedded raster artwork plus a cut outline. It is not a fully vectorized sticker.
        </p>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="font-display text-2xl">When the photo is not enough</h2>
        <p className="text-sm leading-6">
          Glare, blur, and missing pieces stay missing. Sticky will say so instead of redrawing the artwork. Take another photo facing the sticker, with even light, and run it again. The first photo remains available until you remove it or the temporary files expire.
        </p>
      </section>
    </main>
  );
}
