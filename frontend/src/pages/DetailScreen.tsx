import { useEffect, useState } from "react";
import { ArrowLeft, Bookmark, ArrowRight, ShieldCheck } from "lucide-react";
import type { Vacancy } from "../types";
import { SourceTag } from "../components/SourceTag";
import { fmtLabel, formatSalary } from "../lib/format";
import { setBackButton, haptic } from "../lib/telegram";
import { reportVacancy } from "../api/client";
import { useStore } from "../store";

interface Props {
  v: Vacancy;
}

export function DetailScreen({ v }: Props) {
  const { saved, toggleSaved, closeVacancy } = useStore();
  const isSaved = saved.has(v.id);
  const [reportSent, setReportSent] = useState(false);

  useEffect(() => {
    setBackButton(closeVacancy);
    return () => setBackButton(undefined);
  }, [closeVacancy]);

  const onReport = async () => {
    if (reportSent) return;
    try {
      await reportVacancy(v.id);
      setReportSent(true);
    } catch (e) {
      console.error(e);
    }
  };

  const onApply = () => {
    haptic("medium");
    window.open(v.url, "_blank", "noopener");
  };

  return (
    <div className="h-full overflow-y-auto pb-28">
      {/* nav */}
      <div className="flex justify-between items-center px-4 py-2">
        <button
          onClick={closeVacancy}
          className="grid place-items-center"
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: "#181B21",
            border: "1px solid #2A2F38",
          }}
        >
          <ArrowLeft size={18} />
        </button>
        <button
          onClick={() => {
            haptic("light");
            toggleSaved(v.id);
          }}
          className="grid place-items-center"
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: isSaved ? "var(--accent)" : "#181B21",
            border: `1px solid ${isSaved ? "transparent" : "#2A2F38"}`,
          }}
        >
          <Bookmark
            size={18}
            color={isSaved ? "var(--accent-on)" : "#F4F5F7"}
            fill={isSaved ? "var(--accent-on)" : "none"}
          />
        </button>
      </div>

      <div className="px-5 pt-2">
        <div className="flex gap-1.5 mb-3 items-center">
          <SourceTag source={v.source} />
          {v.is_verified && (
            <span
              className="inline-flex items-center gap-0.5 font-mono"
              style={{ color: "#3DDC97", fontSize: 10, fontWeight: 700 }}
            >
              <ShieldCheck size={10} />
              verified
            </span>
          )}
        </div>

        <h1
          className="font-display font-extrabold text-text mb-1.5"
          style={{
            fontSize: 28,
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
          }}
        >
          {v.title}
        </h1>
        <div className="text-text-2 mb-4" style={{ fontSize: 14 }}>
          {v.company || ""}
        </div>

        {/* Salary card */}
        <div
          className="mb-4"
          style={{
            padding: 18,
            borderRadius: 16,
            background:
              "linear-gradient(135deg, var(--accent), color-mix(in oklab, var(--accent) 70%, #000))",
            color: "var(--accent-on)",
          }}
        >
          <div
            className="font-mono mb-1.5"
            style={{
              fontSize: 10,
              letterSpacing: "0.08em",
              opacity: 0.65,
            }}
          >
            ЗАРПЛАТА
          </div>
          <div
            className="font-display font-extrabold"
            style={{ fontSize: 32, letterSpacing: "-0.03em", lineHeight: 1 }}
          >
            {v.salary_from || v.salary_to ? `${formatSalary(v)} ₽` : "не указана"}
            {v.salary_unit && (
              <span
                style={{
                  fontSize: 14,
                  opacity: 0.7,
                  fontWeight: 600,
                  marginLeft: 6,
                }}
              >
                {v.salary_unit}
              </span>
            )}
          </div>
        </div>

        {/* meta grid */}
        <div className="grid grid-cols-2 gap-2 mb-5">
          {[
            ["Город", v.city || "—"],
            ["Формат", fmtLabel(v.format)],
            ["Возраст", `${v.min_age}+`],
            ["Категория", v.category || "—"],
          ].map(([k, val]) => (
            <div
              key={k}
              style={{
                padding: 12,
                background: "#111317",
                border: "1px solid #2A2F38",
                borderRadius: 12,
              }}
            >
              <div
                className="font-mono uppercase text-text-3 mb-1"
                style={{ fontSize: 9, letterSpacing: "0.08em" }}
              >
                {k}
              </div>
              <div
                className="font-display font-semibold text-text"
                style={{ fontSize: 13 }}
              >
                {val}
              </div>
            </div>
          ))}
        </div>

        {v.description && (
          <>
            <h3
              className="font-display font-bold text-text mb-2"
              style={{ fontSize: 14 }}
            >
              Описание
            </h3>
            <p
              className="text-text-2 mb-4 whitespace-pre-line"
              style={{ fontSize: 14, lineHeight: 1.5 }}
            >
              {v.description}
            </p>
          </>
        )}

        <h3
          className="font-display font-bold text-text mb-2"
          style={{ fontSize: 14 }}
        >
          Что нужно
        </h3>
        <ul
          className="text-text-2 mb-5"
          style={{ fontSize: 13, lineHeight: 1.6, paddingLeft: 18 }}
        >
          <li>Возраст {v.min_age}+</li>
          <li>Гибкий график</li>
          <li>Ответственность и пунктуальность</li>
        </ul>

        {v.is_suspect && v.spam_reason && (
          <div
            className="mb-4 p-3 rounded-input border"
            style={{
              borderColor: "rgba(255,181,71,0.4)",
              background: "rgba(255,181,71,0.07)",
              color: "#FFB547",
              fontSize: 12,
            }}
          >
            ⚠️ AI-модерация: {v.spam_reason}
          </div>
        )}

        <button
          onClick={onReport}
          disabled={reportSent}
          className="font-display text-text-3 underline disabled:no-underline disabled:text-ok mb-2"
          style={{ fontSize: 11 }}
        >
          {reportSent ? "Спасибо! Жалоба отправлена" : "Пожаловаться на вакансию"}
        </button>
      </div>

      {/* sticky CTA */}
      <div
        className="absolute left-0 right-0 bottom-0"
        style={{
          padding: "14px 16px 22px",
          background: "linear-gradient(180deg, transparent, #0A0B0D 30%)",
        }}
      >
        <button
          onClick={onApply}
          className="w-full font-display font-extrabold flex items-center justify-center gap-2"
          style={{
            height: 52,
            borderRadius: 16,
            background: "var(--accent)",
            color: "var(--accent-on)",
            fontSize: 16,
            letterSpacing: "-0.01em",
          }}
        >
          Откликнуться <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
