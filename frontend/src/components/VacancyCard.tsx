import { Pin, ShieldCheck, AlertTriangle, MapPin, Eye } from "lucide-react";
import type { Vacancy } from "../types";
import { Salary } from "./Salary";
import { Chip } from "./Chip";
import { SourceTag } from "./SourceTag";
import { fmtLabel, formatPosted } from "../lib/format";
import { useStore } from "../store";

interface Props {
  v: Vacancy;
  onOpen?: () => void;
}

export function VacancyCard({ v, onOpen }: Props) {
  const viewed = useStore((s) => s.viewed.has(v.id));
  const pinned = v.is_featured;
  return (
    <div
      onClick={onOpen}
      className="relative rounded-cardLg p-4 cursor-pointer transition active:scale-[0.99]"
      style={{
        background: pinned
          ? "linear-gradient(180deg, #181B21, #111317)"
          : "#111317",
        border: `1px solid ${pinned ? "rgba(199,247,81,0.25)" : "#2A2F38"}`,
        opacity: viewed && !pinned ? 0.55 : 1,
      }}
    >
      {pinned && (
        <div
          className="absolute -top-px right-3.5 inline-flex items-center gap-1 px-2 py-1 font-mono"
          style={{
            background: "var(--accent)",
            color: "var(--accent-on)",
            borderRadius: "0 0 8px 8px",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.04em",
          }}
        >
          <Pin size={10} />
          PINNED
        </div>
      )}

      {/* top row */}
      <div className="flex justify-between items-start gap-3 mb-2.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <SourceTag source={v.source} />
          {viewed && !pinned && (
            <span
              className="inline-flex items-center gap-0.5 font-mono"
              style={{ color: "#6E7480", fontSize: 10, fontWeight: 700 }}
            >
              <Eye size={10} />
              просмотрено
            </span>
          )}
          {v.is_verified && (
            <span
              className="inline-flex items-center gap-0.5 font-mono"
              style={{ color: "#3DDC97", fontSize: 10, fontWeight: 700 }}
            >
              <ShieldCheck size={10} />
              verified
            </span>
          )}
          {v.is_suspect && (
            <span
              className="inline-flex items-center gap-0.5 font-mono"
              style={{ color: "#FFB547", fontSize: 10, fontWeight: 700 }}
              title={v.spam_reason ?? "AI: возможно реферальная схема"}
            >
              <AlertTriangle size={10} />
              проверьте
            </span>
          )}
        </div>
        <span
          className="font-mono whitespace-nowrap text-text-3"
          style={{ fontSize: 10 }}
        >
          {formatPosted(v.posted_at ?? v.created_at)}
        </span>
      </div>

      <h3
        className="font-display font-bold text-text"
        style={{
          fontSize: 18,
          lineHeight: 1.15,
          letterSpacing: "-0.02em",
          margin: "0 0 4px",
        }}
      >
        {v.title}
      </h3>
      <div className="text-text-2 mb-3.5" style={{ fontSize: 13 }}>
        {v.company || ""}
      </div>

      <div className="mb-3">
        <Salary v={v} />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {v.city && (
          <Chip>
            <MapPin size={12} />
            {v.city}
          </Chip>
        )}
        <Chip>{fmtLabel(v.format)}</Chip>
        <Chip mono>{v.min_age}+</Chip>
      </div>
    </div>
  );
}
