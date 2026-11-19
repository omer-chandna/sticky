/** Desk tools seen from above, drawn to sit on the cutting mat. */

export function CraftKnife({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 460 48" className={className} aria-hidden>
      <defs>
        <linearGradient id="knife-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c9d98e" />
          <stop offset="0.45" stopColor="#8aa83f" />
          <stop offset="1" stopColor="#4d6a1a" />
        </linearGradient>
        <linearGradient id="knife-steel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f4f5f0" />
          <stop offset="0.5" stopColor="#b9beb3" />
          <stop offset="1" stopColor="#7d8377" />
        </linearGradient>
        <pattern id="knurl" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="5" height="5" fill="transparent" />
          <path d="M0 0 V5" stroke="rgba(30,40,12,0.45)" strokeWidth="1.4" />
        </pattern>
      </defs>
      <rect x="4" y="11" width="300" height="26" rx="13" fill="url(#knife-body)" />
      <rect x="150" y="11" width="140" height="26" fill="url(#knurl)" />
      <rect x="4" y="11" width="300" height="26" rx="13" fill="none" stroke="rgba(30,40,12,0.35)" />
      <path d="M300 13 L344 17 L344 31 L300 35 Z" fill="url(#knife-steel)" />
      <path d="M312 14 V34 M322 15 V33" stroke="rgba(40,45,35,0.45)" strokeWidth="2" />
      <path d="M342 18 L380 18 L456 27 L342 31 Z" fill="url(#knife-steel)" />
      <path d="M380 18 L456 27" stroke="#ffffff" strokeWidth="1.5" opacity="0.8" />
      <path d="M342 24.5 L432 25.5" stroke="rgba(60,66,55,0.35)" strokeWidth="1" />
    </svg>
  );
}

/** A 200 mm steel rule, 4 px to the millimetre. */
export function SteelRuler({ className = "" }: { className?: string }) {
  const mm = Array.from({ length: 201 }, (_, i) => i);
  return (
    <svg viewBox="0 0 840 64" className={className} aria-hidden>
      <defs>
        <linearGradient id="ruler-steel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f1f2ec" />
          <stop offset="0.55" stopColor="#d3d7cc" />
          <stop offset="1" stopColor="#a9ae9f" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="840" height="64" rx="4" fill="url(#ruler-steel)" />
      <circle cx="822" cy="32" r="7" fill="#26330f" opacity="0.85" />
      {mm.map((i) => {
        const x = 16 + i * 4;
        const h = i % 10 === 0 ? 20 : i % 5 === 0 ? 14 : 8;
        return <rect key={i} x={x - 0.6} y="0" width="1.2" height={h} fill="#26330f" />;
      })}
      {mm
        .filter((i) => i % 10 === 0)
        .map((i) => (
          <text key={i} x={16 + i * 4} y="40" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="11" fill="#26330f">
            {i / 10}
          </text>
        ))}
      <text x="40" y="56" fontFamily="var(--font-mono)" fontSize="8" letterSpacing="2" fill="#5e6a4e">
        STAINLESS · CM
      </text>
    </svg>
  );
}

export function Pencil({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 300 24" className={className} aria-hidden>
      <rect x="0" y="4" width="20" height="16" rx="3" fill="#b4683f" />
      <rect x="18" y="3" width="14" height="18" fill="#c9cbc2" />
      <rect x="32" y="4" width="210" height="16" fill="#e3b85c" />
      <rect x="32" y="4" width="210" height="5" fill="#f0cf86" />
      <path d="M242 4 L284 12 L242 20 Z" fill="#f1dcb6" />
      <path d="M272 9.8 L292 12 L272 14.2 Z" fill="#26330f" />
    </svg>
  );
}
