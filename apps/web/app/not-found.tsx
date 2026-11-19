import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import { CraftKnife } from "@/components/landing/craft-tools";
import { SiteNav } from "@/components/landing/site-nav";
import { StarSticker } from "@/components/landing/sticker-art";

export default function NotFound() {
  return (
    <div className="dot-grid min-h-screen p-2">
      <SiteNav current="" />
      <main className="cutting-mat relative flex min-h-[calc(100svh-1rem)] items-center justify-center overflow-hidden rounded-3xl px-6 py-32 text-center text-cream">
        <CraftKnife className="on-desk absolute right-[-4%] top-24 hidden w-[34%] rotate-[160deg] md:block" />
        <div className="relative z-10 flex max-w-xl flex-col items-center">
          {/* The empty spot on the backing where a sticker used to be */}
          <div className="relative w-40" aria-hidden>
            <svg viewBox="0 0 120 112" className="w-full">
              <path
                d="M60 8 L74 42 L110 44 L82 67 L92 104 L60 84 L28 104 L38 67 L10 44 L46 42 Z"
                fill="rgba(244,239,226,0.08)"
                stroke="#c9d98e"
                strokeWidth="2"
                strokeDasharray="5 5"
              />
            </svg>
            <StarSticker className="absolute -right-16 -top-6 w-20 rotate-[24deg]" />
          </div>
          <p className="caption-4 mt-8 text-foam">Error 404</p>
          <h1 className="heading-2 hero-cream mt-4">This page peeled off.</h1>
          <p className="lead mt-4 opacity-80">The link may be old, or the address has a typo. Your stickers are still where you left them.</p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row">
            <Link
              href="/"
              className="button-md inline-flex items-center gap-2 rounded-full bg-foam px-6 py-3 text-matcha-deep transition-[transform,background-color] duration-300 ease-base hover:-translate-y-0.5 hover:bg-cream active:scale-[0.98]"
            >
              <ArrowLeft size={18} weight="bold" aria-hidden /> Back to Sticky
            </Link>
            <Link href="/guide" className="button-md rounded-full px-3 py-2 text-cream underline decoration-2 underline-offset-8" style={{ textDecorationColor: "rgba(201,217,142,0.5)" }}>
              Open the print guide
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
