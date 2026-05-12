import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { useStore } from "../store";
import type { Filters } from "../types";
import { setBackButton } from "../lib/telegram";

const CATEGORIES = [
  "Кафе и рестораны",
  "Промоутер",
  "Репетитор и обучение",
  "IT и интернет",
  "Дизайн и творчество",
  "Торговля и продажи",
  "Административная",
  "Доставка",
];

export function FiltersScreen() {
  const { filters, setFilters, resetFilters, setRoute, total, loadInitial } = useStore();
  const [local, setLocal] = useState<Filters>({ ...filters });

  useEffect(() => {
    setBackButton(() => setRoute("feed"));
    return () => setBackButton(undefined);
  }, [setRoute]);

  const apply = () => {
    setFilters(local);
    loadInitial();
    setRoute("feed");
  };

  const reset = () => {
    resetFilters();
    setLocal({
      q: filters.q,
      city: "",
      age: null,
      format: "all",
      salary_from: 0,
      categories: [],
    });
  };

  const toggleCat = (c: string) => {
    setLocal((s) =>
      s.categories.includes(c)
        ? { ...s, categories: s.categories.filter((x) => x !== c) }
        : { ...s, categories: [...s.categories, c] }
    );
  };

  return (
    <div
      className="absolute inset-0 flex items-end"
      style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={() => setRoute("feed")}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full overflow-y-auto"
        style={{
          background: "#111317",
          borderRadius: "24px 24px 0 0",
          padding: "12px 20px 24px",
          maxHeight: "85%",
          border: "1px solid #2A2F38",
          borderBottom: "none",
        }}
      >
        <div
          style={{
            width: 40,
            height: 4,
            background: "#2A2F38",
            borderRadius: 2,
            margin: "0 auto 14px",
          }}
        />

        <div className="flex justify-between items-center mb-4">
          <h2
            className="font-display font-extrabold text-text m-0"
            style={{ fontSize: 22, letterSpacing: "-0.03em" }}
          >
            Фильтры
          </h2>
          <button
            onClick={() => setRoute("feed")}
            className="grid place-items-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 10,
              background: "#23272F",
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Возраст */}
        <FilterLabel>Возраст</FilterLabel>
        <div
          className="flex gap-1.5 p-1 mb-4"
          style={{ background: "#181B21", borderRadius: 12 }}
        >
          {[14, 16, 18].map((a) => {
            const on = local.age === a;
            return (
              <button
                key={a}
                onClick={() =>
                  setLocal((s) => ({ ...s, age: on ? null : (a as 14 | 16 | 18) }))
                }
                className="flex-1 font-display font-bold"
                style={{
                  height: 36,
                  borderRadius: 9,
                  background: on ? "var(--accent)" : "transparent",
                  color: on ? "var(--accent-on)" : "#A8ADB7",
                  fontSize: 14,
                }}
              >
                {a}+
              </button>
            );
          })}
        </div>

        {/* Формат */}
        <FilterLabel>Формат</FilterLabel>
        <div className="flex gap-1.5 mb-4">
          {([
            ["all", "Любой"],
            ["offline", "Офлайн"],
            ["online", "Онлайн"],
          ] as const).map(([k, l]) => {
            const on = local.format === k;
            return (
              <button
                key={k}
                onClick={() => setLocal((s) => ({ ...s, format: k }))}
                className="flex-1 font-display font-semibold"
                style={{
                  height: 38,
                  borderRadius: 12,
                  background: on ? "#F4F5F7" : "#181B21",
                  color: on ? "#0A0B0D" : "#A8ADB7",
                  border: `1px solid ${on ? "transparent" : "#2A2F38"}`,
                  fontSize: 13,
                }}
              >
                {l}
              </button>
            );
          })}
        </div>

        {/* Зарплата */}
        <div className="mb-4">
          <div className="flex justify-between items-baseline mb-2">
            <span
              className="font-mono uppercase text-text-3"
              style={{ fontSize: 10, letterSpacing: "0.08em" }}
            >
              Зарплата от
            </span>
            <span
              className="font-display font-bold"
              style={{ color: "var(--accent)", fontSize: 16 }}
            >
              {local.salary_from} ₽/час
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={1000}
            step={50}
            value={local.salary_from}
            onChange={(e) =>
              setLocal((s) => ({ ...s, salary_from: Number(e.target.value) }))
            }
            className="w-full"
          />
        </div>

        {/* Категории */}
        <FilterLabel>Категории</FilterLabel>
        <div className="flex flex-wrap gap-1.5 mb-5">
          {CATEGORIES.map((c) => {
            const on = local.categories.includes(c);
            return (
              <button
                key={c}
                onClick={() => toggleCat(c)}
                className="font-display font-semibold inline-flex items-center gap-1"
                style={{
                  padding: "8px 12px",
                  borderRadius: 10,
                  background: on ? "var(--accent)" : "#181B21",
                  color: on ? "var(--accent-on)" : "#A8ADB7",
                  border: `1px solid ${on ? "transparent" : "#2A2F38"}`,
                  fontSize: 13,
                }}
              >
                {on && <Check size={12} />}
                {c}
              </button>
            );
          })}
        </div>

        <div className="flex gap-2">
          <button
            onClick={reset}
            className="flex-1 font-display font-semibold"
            style={{
              height: 50,
              borderRadius: 14,
              background: "#181B21",
              color: "#A8ADB7",
              border: "1px solid #2A2F38",
              fontSize: 14,
            }}
          >
            Сбросить
          </button>
          <button
            onClick={apply}
            className="flex-[2] font-display font-extrabold"
            style={{
              height: 50,
              borderRadius: 14,
              background: "var(--accent)",
              color: "var(--accent-on)",
              fontSize: 15,
            }}
          >
            Показать {total} вакансий
          </button>
        </div>
      </div>
    </div>
  );
}

function FilterLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="font-mono uppercase text-text-3 mb-2"
      style={{ fontSize: 10, letterSpacing: "0.08em" }}
    >
      {children}
    </div>
  );
}
