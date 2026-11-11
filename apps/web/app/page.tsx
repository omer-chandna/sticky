"use client";

import { Github } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { BeforeAfter } from "@/components/before-after";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Wordmark } from "@/components/wordmark";
import { setPendingFile } from "@/lib/pending";

const STEPS = [
  { n: "01", title: "Upload", text: "A single sticker, or a whole laptop lid." },
  { n: "02", title: "Restore", text: "Straighten it, lift it off the surface, and clean the photo." },
  { n: "03", title: "Resize", text: "Set millimetres, a border, and a cut outline." },
  { n: "04", title: "Print", text: "A true-size PDF, a PNG, or vectors for Design Space." },
];

export default function HomePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  function take(file: File | undefined) {
    if (!file) return;
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
      setError("Use a JPG, PNG, WebP, or HEIC photograph.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError("That file is over 25 MB. Export a smaller photo and try again.");
      return;
    }
    setPendingFile(file);
    router.push("/studio");
  }

  async function tryExample(kind: "single" | "collection") {
    const response = await fetch(kind === "single" ? "/samples/single.png" : "/samples/collection.png");
    const blob = await response.blob();
    const file = new File([blob], kind === "single" ? "example-sticker.png" : "example-collection.png", { type: "image/png" });
    sessionStorage.setItem("sticky-mode", kind);
    setPendingFile(file);
    router.push("/studio");
  }

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Wordmark />
        <div className="flex items-center gap-1">
          <Link href="/guide" className="rounded-full px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10">
            Print & Cricut
          </Link>
          <a
            href="https://github.com/omer-chandna/sticky"
            className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10"
          >
            <Github size={16} /> Source
          </a>
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl items-center gap-10 px-5 pb-16 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <p className="text-sm uppercase tracking-[0.18em] text-muted">Open source · on your machine</p>
          <h1 className="mt-3 font-display text-5xl leading-[1.05] sm:text-6xl">Your stickers, wherever you go.</h1>
          <p className="mt-5 max-w-xl text-lg text-muted">
            Photograph a sticker you already own. Sticky pulls the artwork off the laptop, straightens it, and gives you a file you can print or cut again.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button variant="primary" onClick={() => document.getElementById("sticker-file")?.click()}>
              Restore a sticker
            </Button>
            <Button onClick={() => void tryExample("single")}>Try an example</Button>
          </div>
        </div>
        <BeforeAfter before="/demo/before.png" after="/demo/after.png" alt="The same sticker after perspective correction and background removal" />
      </main>

      <section className="mx-auto max-w-6xl px-5 pb-16">
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
            take(event.dataTransfer.files?.[0]);
          }}
          className={`block cursor-pointer rounded-3xl border border-dashed px-6 py-12 text-center ${over ? "border-accent bg-accent/5" : "border-line bg-elev"}`}
        >
          <p className="font-display text-3xl">Drop a photograph</p>
          <p className="mt-2 text-muted">JPG, PNG, WebP, or HEIC. One sticker, or a lid full of them. Nothing here requires an account.</p>
          <input
            id="sticker-file"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
            className="sr-only"
            onChange={(event) => take(event.target.files?.[0])}
          />
        </label>
        {error && <p className="mt-3 text-sm text-warn">{error}</p>}
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          <button className="underline decoration-line underline-offset-4" onClick={() => void tryExample("single")}>
            Example: one sticker
          </button>
          <button className="underline decoration-line underline-offset-4" onClick={() => void tryExample("collection")}>
            Example: several stickers
          </button>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-5 pb-16 sm:grid-cols-4">
        {STEPS.map((step) => (
          <article key={step.n} className="rounded-2xl border border-line bg-elev p-4">
            <p className="text-xs tracking-widest text-muted">{step.n}</p>
            <h2 className="mt-2 font-display text-2xl">{step.title}</h2>
            <p className="mt-2 text-sm text-muted">{step.text}</p>
          </article>
        ))}
      </section>

      <footer className="mx-auto flex max-w-6xl flex-col gap-2 px-5 pb-10 text-sm text-muted sm:flex-row sm:justify-between">
        <p>Photos are processed on the Sticky server you run. They are not sent to a third party, and they expire after a few hours.</p>
        <p>MIT license</p>
      </footer>
    </div>
  );
}
