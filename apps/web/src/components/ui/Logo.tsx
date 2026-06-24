/** DocOS brand mark: a document sheet with a verification check — the product's
 * "trusted document" idea in one glyph. Uses currentColor-friendly fixed brand hues. */
export function LogoMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="34" height="34" rx="9" fill="#2451e6" />
      <rect x="1" y="1" width="34" height="34" rx="9" fill="url(#docframe-g)" fillOpacity="0.35" />
      <path
        d="M12 9.5h7.2c.5 0 1 .2 1.3.6l4 4c.3.3.5.8.5 1.3V25c0 .8-.7 1.5-1.5 1.5H12c-.8 0-1.5-.7-1.5-1.5V11c0-.8.7-1.5 1.5-1.5Z"
        fill="white"
      />
      <path
        d="m15.3 18.4 2 2 4-4.3"
        stroke="#13b48d"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient id="docframe-g" x1="1" y1="1" x2="35" y2="35" gradientUnits="userSpaceOnUse">
          <stop stopColor="white" stopOpacity="0.5" />
          <stop offset="1" stopColor="white" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}

/** Wordmark + mark lockup for the header. */
export function Logo({ subtitle }: { subtitle?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <LogoMark />
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold leading-tight text-ink sm:text-base">
          DocOS
        </span>
        {subtitle && <span className="block truncate text-xs text-slate-500">{subtitle}</span>}
      </span>
    </span>
  );
}
