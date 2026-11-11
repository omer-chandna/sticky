export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-display text-2xl tracking-tight ${className}`}>
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
        <path d="M4 3.5h10.2L18.5 8v10.5H4V3.5z" fill="currentColor" />
        <path d="M14.2 3.5 18.5 8h-4.3V3.5z" fill="var(--bg)" />
      </svg>
      Sticky
    </span>
  );
}
