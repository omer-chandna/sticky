"use client";

import { Camera, LockSimple, Printer, Ruler, Scissors, SealCheck, Sparkle, UploadSimple } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { HeroMat } from "@/components/landing/hero-mat";
import { CraftHero } from "@/components/landing/craft-hero";
import { CraftKnife, SteelRuler } from "@/components/landing/craft-tools";
import { CloudSticker, HelloSticker, StarSticker } from "@/components/landing/sticker-art";
import { Reveal } from "@/components/landing/reveal";
import { SiteNav } from "@/components/landing/site-nav";
import { TaglineReveal } from "@/components/landing/tagline-reveal";
import { Wordmark } from "@/components/wordmark";
import { checkPhotos, setPendingFile, setPendingFiles } from "@/lib/pending";

const SOURCE = "https://github.com/omer-chandna/sticky";

/* Fixed colour cards. Each pairs a fill with its own ink so it reads in both themes. */
const BENEFITS = [
  {
    icon: SealCheck,
    title: "Faithful, not redrawn",
    text: "Sticky restores what your photo shows. Glare, blur, and missing pieces stay missing, and it tells you so instead of inventing artwork.",
    tone: "cutting-mat text-cream lg:col-span-2 lg:row-span-2",
    big: true,
  },
  {
    icon: Ruler,
    title: "True to the millimetre",
    text: "Set millimetres, centimetres, or inches. The sheet PDF prints at real page size and aims for 300 DPI.",
    tone: "bg-foam text-[#26330f]",
  },
  {
    icon: Scissors,
    title: "Ready for your cutter",
    text: "A cut outline SVG and a transparent PNG for Print Then Cut in Cricut Design Space.",
    tone: "bg-pop text-[#3a2a08]",
  },
  {
    icon: LockSimple,
    title: "Stays on your machine",
    text: "Photos are processed on the Sticky server you run. Nothing goes to a third party, and files expire after a few hours.",
    tone: "bg-clay text-cream lg:col-span-2",
  },
];

const STEPS = [
  { icon: Camera, title: "Photograph the old one", text: "A JPG, PNG, WebP, or HEIC photo of one sticker, the whole lid, or a few close ups to combine." },
  { icon: Sparkle, title: "Restore each sticker", text: "Sticky finds each outline, straightens four sided stickers, and lifts the artwork off the surface." },
  { icon: Printer, title: "Stick them on the new one", text: "Set the size, add a border and a cut line, then print on sticker paper or send the cut file to your cutter." },
];

const FAQ = [
  {
    q: "Why copy stickers I already own?",
    a: "Most stickers tear when you peel them, and many came from a gig, a trip, or a friend, so you cannot buy them again. A photo of the old laptop is enough to bring them with you.",
  },
  { q: "Do I need an account?", a: "No. There is no account and no API key. Open the page, drop in a photo, and download your files." },
  {
    q: "Where do my photos go?",
    a: "To the Sticky server you run, usually your own computer. They are not sent to a third party, and temporary files expire after a few hours.",
  },
  {
    q: "Can it fix a blurry or glary photo?",
    a: "Only partly. Cleanup and sharpness sliders help, but Sticky will not redraw detail the photo does not have. Take another photo facing the sticker in even light for the best result.",
  },
  {
    q: "Does it work with Cricut?",
    a: "Yes, as a file source. Import the transparent PNG into Design Space and use Print Then Cut. Sticky does not draw Cricut registration marks or talk to the machine.",
  },
  {
    q: "How big can I print?",
    a: "Any size that fits a Letter or A4 sheet. Exports aim for 300 DPI at the size you enter. Enlarging a small photo will not add detail that was not there.",
  },
  {
    q: "Can I restore several stickers at once?",
    a: "Yes. Upload a photo of a whole laptop lid, or several overlapping close ups that Sticky combines. It proposes an outline for each sticker, and you can adjust or draw your own.",
  },
  { q: "Is it free?", a: "Yes. Sticky is open source under the MIT license. The code is on GitHub." },
];

export default function HomePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [loading, setLoading] = useState<"single" | "collection" | null>(null);

  function take(list: FileList | null | undefined) {
    const files = Array.from(list ?? []);
    if (!files.length) return;
    const problem = checkPhotos(files);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    // Several photos are close-ups of the same lid; they are combined and opened as a collection.
    if (files.length > 1) sessionStorage.setItem("sticky-mode", "collection");
    setPendingFiles(files);
    router.push("/studio");
  }

  async function tryExample(kind: "single" | "collection") {
    setLoading(kind);
    try {
      const response = await fetch(kind === "single" ? "/samples/single.png" : "/samples/collection.png");
      const blob = await response.blob();
      const file = new File([blob], kind === "single" ? "example-sticker.png" : "example-collection.png", { type: "image/png" });
      sessionStorage.setItem("sticky-mode", kind);
      setPendingFile(file);
      router.push("/studio");
    } catch {
      setLoading(null);
      setError("The example could not load. Check that the web server is running and try again.");
    }
  }

  const pick = () => document.getElementById("sticker-file")?.click();

  return (
    <div className="dot-grid min-h-screen overflow-x-hidden">
      <a
        href="#main"
        className="button-sm fixed left-4 top-4 z-50 -translate-y-24 rounded-full bg-ink px-3 py-2 text-bg transition-transform duration-300 ease-base focus:translate-y-0"
      >
        Skip to content
      </a>
      <SiteNav />

      <main id="main">
        <CraftHero onPick={pick} onExample={() => void tryExample("single")} loading={loading === "single"} />

        {/* Photo to sticker */}
        <section className="px-4 pt-24" aria-labelledby="pour-heading">
          <Reveal className="mx-auto mb-12 max-w-5xl text-center">
            <p className="caption-4 text-accent">See it work</p>
            <h2 id="pour-heading" className="heading-2 mt-4">
              From the old lid
              <br />
              to a fresh sheet.
            </h2>
          </Reveal>
          <Reveal>
            <HeroMat />
          </Reveal>
        </section>

        {/* Drop zone */}
        <section className="px-4 py-24" aria-labelledby="drop-heading">
          <Reveal className="mx-auto max-w-5xl">
            <label
              htmlFor="sticker-file"
              onDragOver={(event) => {
                event.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(event) => {
                event.preventDefault();
                setOver(false);
                take(event.dataTransfer.files);
              }}
              className={`group flex cursor-pointer flex-col items-center rounded-3xl border-2 border-dashed px-6 py-16 text-center transition-[background-color,border-color,transform] duration-300 ease-base hover:-translate-y-0.5 ${
                over ? "scale-[1.01] border-accent bg-elev" : "border-dot bg-elev hover:border-accent"
              }`}
            >
              <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-foam text-[#26330f] transition-transform duration-500 ease-base group-hover:-rotate-6">
                <UploadSimple size={28} weight="bold" aria-hidden />
              </span>
              <span id="drop-heading" className="heading-5 mt-6">
                {over ? "Let go to start restoring" : "Drop a photograph here"}
              </span>
              <span className="body-6 mt-2 max-w-md text-muted">
                JPG, PNG, WebP, or HEIC, up to 25 MB. One sticker, a lid full of them, or several overlapping close ups to combine for more detail.
              </span>
              <span className="button-sm mt-6 inline-flex items-center gap-2 rounded-full bg-accent px-3 py-2 text-accent-ink transition-transform duration-300 ease-base group-hover:-translate-y-px">
                <UploadSimple size={16} weight="bold" aria-hidden /> Choose photos
              </span>
              <input
                id="sticker-file"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
                className="sr-only"
                multiple
                onChange={(event) => take(event.target.files)}
              />
            </label>
            {error && (
              <p role="alert" className="body-6 mt-4 text-center text-warn">
                {error}
              </p>
            )}
            <div className="body-6 mt-4 flex flex-wrap justify-center gap-4 text-muted">
              <span>No photo handy?</span>
              <button className="underline decoration-dot underline-offset-4 hover:text-ink" onClick={() => void tryExample("single")}>
                {loading === "single" ? "Loading…" : "Try one sticker"}
              </button>
              <button className="underline decoration-dot underline-offset-4 hover:text-ink" onClick={() => void tryExample("collection")}>
                {loading === "collection" ? "Loading…" : "Try a laptop lid"}
              </button>
            </div>
          </Reveal>
        </section>

        {/* Tagline reveal */}
        <section className="relative px-4 py-24" aria-label="What Sticky does">
          <StarSticker className="absolute left-[8%] top-12 hidden w-16 -rotate-12 md:block" />
          <CloudSticker className="absolute bottom-8 right-[10%] hidden w-20 rotate-6 md:block" />
          <TaglineReveal lines={["You moved your photos.", "You moved your messages.", "Now move your stickers."]} />
        </section>

        {/* Benefits bento */}
        <section className="px-4 py-24" aria-labelledby="benefits-heading">
          <div className="mx-auto max-w-5xl">
            <Reveal>
              <p className="caption-4 text-accent">Why Sticky</p>
              <h2 id="benefits-heading" className="heading-2 mt-4 max-w-[680px]">
                The same sticker,
                <br />
                not a lookalike.
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-4 lg:grid-cols-4">
              {BENEFITS.map((benefit, i) => (
                <Reveal
                  as="article"
                  key={benefit.title}
                  delay={i * 80}
                  className={`group relative flex flex-col justify-between overflow-hidden rounded-3xl p-8 transition-transform duration-500 ease-base hover:-translate-y-1 ${benefit.tone}`}
                >
                  <benefit.icon size={benefit.big ? 40 : 28} weight="bold" aria-hidden />
                  <div className={benefit.big ? "mt-24" : "mt-8"}>
                    <h3 className={benefit.big ? "heading-3" : "heading-5"}>{benefit.title}</h3>
                    <p className={`mt-2 opacity-80 ${benefit.big ? "body-3 max-w-sm" : "body-6"}`}>{benefit.text}</p>
                  </div>
                  {benefit.big && (
                    <HelloSticker className="absolute -right-4 top-8 w-36 rotate-12 transition-transform duration-500 ease-base group-hover:rotate-6" />
                  )}
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="scroll-mt-24 px-4 py-24" aria-labelledby="how-heading">
          <div className="mx-auto max-w-5xl">
            <Reveal>
              <p className="caption-4 text-accent">How it works</p>
              <h2 id="how-heading" className="heading-2 mt-4">Old laptop to new, in three steps.</h2>
            </Reveal>
            <ol className="mt-12 grid gap-4 sm:grid-cols-3">
              {STEPS.map((step, i) => (
                <Reveal as="li" key={step.title} delay={i * 100} className="cutting-mat relative rounded-3xl p-8 text-cream">
                  <span className="font-mono text-6xl font-medium text-foam">0{i + 1}</span>
                  <step.icon size={24} weight="bold" className="absolute right-8 top-8 text-pop" aria-hidden />
                  <h3 className="heading-5 mt-8">{step.title}</h3>
                  <p className="body-6 mt-2 opacity-70">{step.text}</p>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="scroll-mt-24 px-4 py-24" aria-labelledby="faq-heading">
          <div className="mx-auto grid max-w-5xl gap-12 lg:grid-cols-[1fr_1.6fr]">
            <Reveal>
              <p className="caption-4 text-accent">Questions</p>
              <h2 id="faq-heading" className="heading-2 mt-4">Before you peel.</h2>
              <p className="body-3 mt-4 text-muted">
                More on printing and Cricut in the{" "}
                <Link href="/guide" className="text-ink underline decoration-dot underline-offset-4 hover:decoration-accent">
                  print guide
                </Link>
                .
              </p>
            </Reveal>
            <Reveal className="flex flex-col gap-2">
              {FAQ.map((item) => (
                <details key={item.q} className="group rounded-2xl border border-line bg-elev px-6 py-4 open:pb-6">
                  <summary className="title-2 flex cursor-pointer list-none items-center justify-between gap-4 rounded-lg">
                    {item.q}
                    <span
                      aria-hidden
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-foam text-xl text-[#26330f] transition-transform duration-500 ease-base group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <p className="body-3 mt-2 text-muted">{item.a}</p>
                </details>
              ))}
            </Reveal>
          </div>
        </section>

        {/* Final CTA */}
        <section className="px-2 pb-2" aria-labelledby="cta-heading">
          <Reveal className="cutting-mat relative overflow-hidden rounded-3xl px-6 py-24 text-center text-cream sm:py-32">
            <h2 id="cta-heading" className="heading-2 hero-cream relative z-10 mx-auto max-w-[680px] sm:text-6xl">
              Bring your stickers
              <br />
              to the next laptop.
            </h2>
            <p className="body-3 relative z-10 mx-auto mt-4 max-w-md opacity-80">Free and open source. No account, and your photos stay on your machine.</p>
            <button
              type="button"
              onClick={pick}
              className="button-md relative z-10 mt-8 inline-flex items-center gap-2 rounded-full bg-foam px-6 py-3 text-matcha-deep transition-[transform,background-color] duration-300 ease-base hover:-translate-y-0.5 hover:bg-cream active:scale-[0.98]"
            >
              <UploadSimple size={18} weight="bold" aria-hidden /> Restore a sticker
            </button>
            <SteelRuler className="on-desk absolute -bottom-2 left-[-4%] hidden w-[60%] rotate-[4deg] sm:block" />
            <CraftKnife className="on-desk absolute right-[2%] top-2 hidden w-[28%] rotate-[164deg] sm:block" />
            <StarSticker className="absolute bottom-16 right-12 hidden w-20 -rotate-12 md:block" />
          </Reveal>
          <footer className="flex flex-col gap-4 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
            <Wordmark className="text-xl" />
            <nav aria-label="Footer" className="body-6 flex flex-wrap gap-4 text-muted">
              <Link href="/guide" className="hover:text-ink">
                Print and Cricut guide
              </Link>
              <a href={SOURCE} className="hover:text-ink">
                Source on GitHub
              </a>
              <a href={`${SOURCE}/blob/main/LICENSE`} className="hover:text-ink">
                MIT license
              </a>
            </nav>
          </footer>
        </section>
      </main>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: FAQ.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
          }),
        }}
      />
    </div>
  );
}
