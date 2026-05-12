import { useEffect, useRef, useState } from "react";
import { Search, Filter, Bell, Flame, RotateCw } from "lucide-react";
import { GrindyWordmark } from "../components/Logo";
import { VacancyCard } from "../components/VacancyCard";
import { useStore } from "../store";
import { usePullToRefresh } from "../lib/usePullToRefresh";

export function FeedScreen() {
  const {
    vacancies,
    cursor,
    loading,
    total,
    filters,
    setQuery,
    setRoute,
    openVacancy,
    loadMore,
    loadInitial,
  } = useStore();
  const [localQ, setLocalQ] = useState(filters.q);

  // debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      if (localQ !== filters.q) {
        setQuery(localQ);
        loadInitial();
      }
    }, 250);
    return () => clearTimeout(t);
  }, [localQ, filters.q, setQuery, loadInitial]);

  const { ref: scrollRef, pull, refreshing } = usePullToRefresh({
    onRefresh: loadInitial,
  });

  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !cursor) return;
    const obs = new IntersectionObserver(
      (e) => {
        if (e[0]?.isIntersecting) loadMore();
      },
      { rootMargin: "300px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [cursor, loadMore]);

  const activeFilters = [
    filters.age,
    filters.format !== "all" ? filters.format : null,
    filters.salary_from > 0 ? "salary" : null,
    ...filters.categories,
  ].filter(Boolean).length;

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto pb-24 relative">
      {/* Pull-to-refresh indicator */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: pull,
          opacity: pull > 0 || refreshing ? 1 : 0,
          transition: refreshing ? "height 0.2s" : "none",
          pointerEvents: "none",
          zIndex: 1,
        }}
      >
        <RotateCw
          size={20}
          color="#A8ADB7"
          style={{
            transform: `rotate(${pull * 4}deg)`,
            animation: refreshing ? "spin 1s linear infinite" : undefined,
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>

      <div
        style={{
          transform: `translateY(${pull}px)`,
          transition: refreshing ? "transform 0.2s" : "none",
        }}
      >
        {/* Header */}
        <div className="px-4 pt-2 pb-3">
          <div className="flex items-center justify-between mb-3.5">
            <GrindyWordmark size={20} />
            <button
              className="relative grid place-items-center"
              style={{
                width: 36,
                height: 36,
                borderRadius: 12,
                background: "#181B21",
                border: "1px solid #2A2F38",
              }}
            >
              <Bell size={18} />
              <span
                className="absolute"
                style={{
                  top: 8,
                  right: 8,
                  width: 7,
                  height: 7,
                  borderRadius: 4,
                  background: "var(--accent)",
                }}
              />
            </button>
          </div>

          <div className="flex gap-2">
            <div
              className="flex-1 flex items-center gap-2.5 px-3.5"
              style={{
                height: 44,
                borderRadius: 14,
                background: "#181B21",
                border: "1px solid #2A2F38",
              }}
            >
              <Search size={18} color="#6E7480" />
              <input
                value={localQ}
                onChange={(e) => setLocalQ(e.target.value)}
                placeholder="Бариста, курьер, репетитор…"
                className="bg-transparent outline-none flex-1 min-w-0 text-text font-display"
                style={{ fontSize: 14 }}
              />
            </div>
            <button
              onClick={() => setRoute("filters")}
              className="relative grid place-items-center"
              style={{
                width: 44,
                height: 44,
                borderRadius: 14,
                background: "#181B21",
                border: "1px solid #2A2F38",
              }}
            >
              <Filter size={18} />
              {activeFilters > 0 && (
                <span
                  className="absolute font-mono grid place-items-center"
                  style={{
                    top: 6,
                    right: 6,
                    background: "var(--accent)",
                    color: "var(--accent-on)",
                    fontSize: 9,
                    fontWeight: 700,
                    minWidth: 14,
                    height: 14,
                    borderRadius: 7,
                    padding: "0 4px",
                  }}
                >
                  {activeFilters}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Hero */}
        <div
          className="mx-4 mb-3.5 flex items-center justify-between"
          style={{
            padding: "14px 16px",
            background: "var(--accent)",
            color: "var(--accent-on)",
            borderRadius: 16,
          }}
        >
          <div>
            <div
              className="font-mono uppercase"
              style={{ fontSize: 10, letterSpacing: "0.08em", opacity: 0.7 }}
            >
              сегодня
            </div>
            <div
              className="font-display font-extrabold"
              style={{
                fontSize: 24,
                letterSpacing: "-0.03em",
                lineHeight: 1.05,
              }}
            >
              {total} свежих
              <br />
              вакансий
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono" style={{ fontSize: 10, opacity: 0.7 }}>
              до 19:00
            </div>
            <div
              className="inline-flex items-center gap-1 font-display font-bold"
              style={{ fontSize: 14 }}
            >
              <Flame size={14} /> вечерняя подборка
            </div>
          </div>
        </div>

        {/* List */}
        <div className="flex flex-col gap-2.5 px-4">
          {vacancies.map((v) => (
            <VacancyCard key={v.id} v={v} onOpen={() => openVacancy(v)} />
          ))}
          {!loading && vacancies.length === 0 && (
            <div
              className="text-center py-8 font-mono text-text-3"
              style={{ fontSize: 11 }}
            >
              — ничего не нашлось —
            </div>
          )}
          {cursor && <div ref={sentinel} className="h-2" />}
          {loading && (
            <div
              className="text-center py-5 font-mono text-text-3"
              style={{ fontSize: 11 }}
            >
              загружаю…
            </div>
          )}
          {!cursor && vacancies.length > 0 && (
            <div
              className="text-center py-5 font-mono text-text-3"
              style={{ fontSize: 11 }}
            >
              — конец ленты —
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
