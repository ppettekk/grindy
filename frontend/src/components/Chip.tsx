import type { ReactNode } from "react";
import { cn } from "../lib/cn";

interface Props {
  children: ReactNode;
  accent?: boolean;
  ghost?: boolean;
  mono?: boolean;
  onClick?: () => void;
  className?: string;
}

export function Chip({
  children,
  accent,
  ghost,
  mono,
  onClick,
  className,
}: Props) {
  const Wrap = onClick ? "button" : "span";
  return (
    <Wrap
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-chip whitespace-nowrap leading-none",
        "px-[10px] py-[6px]",
        mono ? "font-mono" : "font-display",
        mono ? "text-[11px] font-semibold" : "text-[12px] font-semibold",
        accent
          ? "bg-[color:var(--accent)] text-[color:var(--accent-on)]"
          : ghost
          ? "border border-line text-text-2"
          : "bg-bg3 text-text-2",
        onClick && "cursor-pointer",
        className
      )}
      style={{ border: ghost ? "1px solid #2A2F38" : undefined }}
    >
      {children}
    </Wrap>
  );
}
