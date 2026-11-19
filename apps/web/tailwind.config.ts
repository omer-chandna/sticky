import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        elev: "var(--elev)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        line: "var(--line)",
        dot: "var(--dot)",
        pop: "var(--pop)",
        matcha: "var(--matcha)",
        "matcha-deep": "var(--matcha-deep)",
        foam: "var(--foam)",
        sky: "var(--sky)",
        punch: "var(--punch)",
        label: "var(--label)",
        clay: "var(--clay)",
        cream: "var(--cream)",
        accent: "var(--accent)",
        "accent-ink": "var(--accent-ink)",
        good: "var(--good)",
        warn: "var(--warn)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        display: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 16px 40px rgba(27, 36, 24, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
