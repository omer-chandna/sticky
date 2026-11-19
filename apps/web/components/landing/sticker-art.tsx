/**
 * Original sticker artwork in the matcha palette. Flat fills, one ink line, no gradients.
 * Pass `cut` to add the white die cut border used for stickers lying loose on the mat.
 */

const INK = "#26330f";
const MATCHA = "#8aa83f";
const FOAM = "#c9d98e";
const CREAM = "#f4efe2";
const BAMBOO = "#e3b85c";

type Props = { className?: string; cut?: boolean };
const cls = (className = "", cut = true) => `${cut ? "die-cut " : ""}${className}`;

/** Round badge with its slogan set around the rim. */
export function BadgeSticker({ className, cut }: Props) {
  return (
    <svg viewBox="0 0 200 200" className={cls(className, cut)} aria-hidden>
      <defs>
        <path id="badge-rim" d="M100 100 m-70 0 a70 70 0 1 1 140 0 a70 70 0 1 1 -140 0" />
      </defs>
      <circle cx="100" cy="100" r="96" fill={INK} />
      <circle cx="100" cy="100" r="86" fill="none" stroke={FOAM} strokeWidth="1.5" strokeDasharray="3 5" />
      <text fontFamily="var(--font-mono)" fontSize="15" fill={FOAM}>
        <textPath href="#badge-rim" startOffset="0" textLength="428" lengthAdjust="spacing">
          PRINT · CUT · STICK · REPEAT ·
        </textPath>
      </text>
      <circle cx="100" cy="100" r="48" fill={MATCHA} />
      <path d="M78 70 h34 l14 14 v46 h-48 z" fill={CREAM} stroke={INK} strokeWidth="3" strokeLinejoin="round" />
      <path d="M112 70 v14 h14" fill={FOAM} stroke={INK} strokeWidth="3" strokeLinejoin="round" />
      <path d="M88 104 q12 10 24 0" fill="none" stroke={INK} strokeWidth="3.5" strokeLinecap="round" />
      <circle cx="92" cy="94" r="3.5" fill={INK} />
      <circle cx="108" cy="94" r="3.5" fill={INK} />
    </svg>
  );
}

export function StarSticker({ className, cut }: Props) {
  return (
    <svg viewBox="0 0 120 120" className={cls(className, cut)} aria-hidden>
      <path
        d="M60 8 L74 42 L110 44 L82 67 L92 104 L60 84 L28 104 L38 67 L10 44 L46 42 Z"
        fill={BAMBOO}
        stroke={INK}
        strokeWidth="4"
        strokeLinejoin="round"
      />
      <path d="M40 52 L48 50" stroke={CREAM} strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export function HelloSticker({ className, cut }: Props) {
  return (
    <svg viewBox="0 0 160 110" className={cls(className, cut)} aria-hidden>
      <path d="M14 10 H146 a10 10 0 0 1 10 10 V70 a10 10 0 0 1 -10 10 H60 L34 102 L38 80 H14 a10 10 0 0 1 -10 -10 V20 a10 10 0 0 1 10 -10 Z" fill={CREAM} stroke={INK} strokeWidth="4" strokeLinejoin="round" />
      <text x="80" y="56" textAnchor="middle" fontFamily="var(--font-sans)" fontWeight="600" fontSize="30" letterSpacing="-1" fill={INK}>
        hello
      </text>
    </svg>
  );
}

export function CloudSticker({ className, cut }: Props) {
  return (
    <svg viewBox="0 0 140 96" className={cls(className, cut)} aria-hidden>
      <path
        d="M36 86 C18 86 6 74 6 59 C6 45 17 34 31 34 C34 17 48 6 66 6 C84 6 98 18 101 34 C118 34 134 46 134 62 C134 76 122 86 106 86 Z"
        fill={CREAM}
        stroke={INK}
        strokeWidth="4"
        strokeLinejoin="round"
      />
      <path d="M48 30 q8 -10 20 -10" fill="none" stroke={FOAM} strokeWidth="5" strokeLinecap="round" />
      <circle cx="56" cy="56" r="4" fill={INK} />
      <circle cx="84" cy="56" r="4" fill={INK} />
      <path d="M62 66 q8 6 16 0" fill="none" stroke={INK} strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  );
}

/** A square label, used for the sticker with its corner peeled up. */
export function LabelSticker({ className, cut }: Props) {
  return (
    <svg viewBox="0 0 140 140" className={cls(className, cut)} aria-hidden>
      <rect x="4" y="4" width="132" height="132" rx="10" fill={FOAM} stroke={INK} strokeWidth="4" />
      <text x="70" y="62" textAnchor="middle" fontFamily="var(--font-sans)" fontWeight="600" fontSize="22" fill={INK}>
        made
      </text>
      <text x="70" y="88" textAnchor="middle" fontFamily="var(--font-sans)" fontWeight="600" fontSize="22" fill={INK}>
        at home
      </text>
      <path d="M40 106 H100" stroke={MATCHA} strokeWidth="6" strokeLinecap="round" />
    </svg>
  );
}
