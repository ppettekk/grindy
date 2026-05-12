interface MarkProps {
  size?: number;
  accent?: string;
  dark?: string;
}

export function GrindyMark({
  size = 28,
  accent = "var(--accent)",
  dark = "#F4F5F7",
}: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-label="Grindy"
    >
      <rect
        x="2.5"
        y="9"
        width="19"
        height="6"
        rx="3"
        fill={dark}
        transform="rotate(-22 12 12)"
      />
      <rect
        x="2.5"
        y="9"
        width="19"
        height="6"
        rx="3"
        fill={accent}
        transform="rotate(22 12 12)"
      />
    </svg>
  );
}

interface WordmarkProps {
  size?: number;
  withMark?: boolean;
  className?: string;
}

export function GrindyWordmark({
  size = 22,
  withMark = true,
  className = "",
}: WordmarkProps) {
  return (
    <span
      className={`inline-flex items-center text-text font-display font-extrabold tracking-display leading-none ${className}`}
      style={{ gap: size * 0.32, fontSize: size }}
    >
      {withMark && <GrindyMark size={size * 1.15} />}
      <span>
        grindy
        <span style={{ color: "var(--accent)" }}>.</span>
      </span>
    </span>
  );
}
