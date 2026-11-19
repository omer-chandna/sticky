"use client";

import { useEffect, useRef } from "react";

/**
 * Large tagline whose words move from a muted tone to full ink, one at a time,
 * as each crosses a trigger line. Scroll work is throttled through requestAnimationFrame.
 */
export function TaglineReveal({ lines }: { lines: string[] }) {
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const words = Array.from(root.querySelectorAll<HTMLSpanElement>("[data-word]"));
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      words.forEach((word) => (word.style.opacity = "1"));
      return;
    }

    let frame = 0;
    let active = false;
    const update = () => {
      frame = 0;
      const trigger = window.innerHeight * 0.72;
      words.forEach((word) => {
        const on = word.getBoundingClientRect().top < trigger;
        word.style.opacity = on ? "1" : "0.3";
      });
    };
    const onScroll = () => {
      if (active && !frame) frame = requestAnimationFrame(update);
    };
    const observer = new IntersectionObserver(([entry]) => {
      active = entry.isIntersecting;
      if (active) update();
    });
    observer.observe(root);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <p ref={ref} className="heading-2 mx-auto max-w-[680px] text-center">
      {lines.map((line, i) => (
        <span key={i} className="block">
          {line.split(" ").map((word, j) => (
            <span
              key={j}
              data-word
              className="inline-block transition-opacity duration-500 ease-base"
              style={{ opacity: 0.3 }}
            >
              {word}
              {j < line.split(" ").length - 1 ? " " : ""}
            </span>
          ))}{" "}
        </span>
      ))}
    </p>
  );
}
