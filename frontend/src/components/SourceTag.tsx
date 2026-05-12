import type { Source } from "../types";
import { SOURCE_LABEL } from "../lib/format";

interface Props {
  source: Source | string;
}

export function SourceTag({ source }: Props) {
  const label = SOURCE_LABEL[source] ?? source;
  const isDirect = source === "direct";
  return (
    <span
      className="font-mono lowercase whitespace-nowrap"
      style={{
        fontSize: 10,
        lineHeight: 1,
        letterSpacing: "0.04em",
        color: isDirect ? "var(--accent)" : "#6E7480",
      }}
    >
      {label}
    </span>
  );
}
