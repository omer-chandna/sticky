"use client";

import { GithubLogo } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Wordmark } from "@/components/wordmark";

const LINKS = [
  { href: "/#how", label: "How it works" },
  { href: "/#faq", label: "Questions" },
  { href: "/guide", label: "Print and Cricut" },
];

const SOURCE = "https://github.com/omer-chandna/sticky";

export function SiteNav({ current = "/" }: { current?: string }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <nav
        aria-label="Main"
        className="glass fixed inset-x-4 top-4 z-40 mx-auto flex max-w-max items-center gap-2 rounded-full border border-line py-2 pl-4 pr-2 sm:inset-x-0"
      >
        <Link href="/" aria-current={current === "/" ? "page" : undefined} className="mr-2 rounded-full">
          <Wordmark className="text-xl" />
        </Link>
        <ul className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={current === link.href ? "page" : undefined}
                className="title-4 block rounded-full px-3 py-2 text-muted transition-colors duration-300 ease-base hover:bg-black/5 hover:text-ink aria-[current=page]:bg-foam aria-[current=page]:text-[#26330f] dark:hover:bg-white/10"
              >
                {link.label}
              </Link>
            </li>
          ))}
          <li>
            <a
              href={SOURCE}
              className="title-4 flex items-center gap-2 rounded-full px-3 py-2 text-muted transition-colors duration-300 ease-base hover:text-ink"
            >
              <GithubLogo size={16} weight="bold" aria-hidden /> Source
            </a>
          </li>
        </ul>
        <ThemeToggle />
        <button
          type="button"
          className="relative flex h-10 w-10 items-center justify-center rounded-full md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          <span
            className={`absolute h-0.5 w-5 rounded-full bg-ink transition-transform duration-500 ease-base ${open ? "rotate-45" : "-translate-y-1"}`}
          />
          <span
            className={`absolute h-0.5 w-5 rounded-full bg-ink transition-transform duration-500 ease-base ${open ? "-rotate-45" : "translate-y-1"}`}
          />
        </button>
      </nav>

      <div
        id="mobile-menu"
        className={`fixed inset-0 z-30 backdrop-blur-xl transition-opacity duration-500 ease-base md:hidden ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        style={{ backgroundColor: "color-mix(in srgb, var(--bg) 94%, transparent)" }}
        aria-hidden={!open}
      >
        <ul className="flex h-full flex-col justify-center gap-2 px-6">
          {[...LINKS, { href: SOURCE, label: "Source" }].map((link, i) => (
            <li
              key={link.href}
              className="transition-[opacity,transform] duration-500 ease-base"
              style={{
                opacity: open ? 1 : 0,
                transform: open ? "none" : "translateY(24px)",
                transitionDelay: open ? `${Math.min(i * 60, 400)}ms` : "0ms",
              }}
            >
              <a href={link.href} tabIndex={open ? 0 : -1} onClick={() => setOpen(false)} className="heading-3 block py-2">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
