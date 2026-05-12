import { Sparkles } from "lucide-react";
import { useStore } from "../store";

export function EmptyScreen() {
  const { setRoute, resetFilters, loadInitial } = useStore();
  return (
    <div className="h-full overflow-y-auto px-6">
      <div
        className="text-center"
        style={{
          margin: "40px 0",
          padding: "32px 20px",
          background: "#111317",
          border: "1px dashed #2A2F38",
          borderRadius: 20,
        }}
      >
        <div
          className="grid place-items-center mx-auto mb-4"
          style={{
            width: 64,
            height: 64,
            borderRadius: 32,
            background: "var(--accent)",
            color: "var(--accent-on)",
          }}
        >
          <Sparkles size={28} />
        </div>
        <h2
          className="font-display font-extrabold text-text"
          style={{
            fontSize: 22,
            letterSpacing: "-0.03em",
            margin: "0 0 8px",
          }}
        >
          Пока тихо.
          <br />
          Но это ненадолго.
        </h2>
        <p className="text-text-2 mb-4" style={{ fontSize: 14, lineHeight: 1.4 }}>
          Под твои фильтры сегодня ничего нет. Утром в 9:00 пришлём свежую подборку — обещаем.
        </p>
        <button
          onClick={() => {
            resetFilters();
            loadInitial();
            setRoute("feed");
          }}
          className="font-display font-bold"
          style={{
            height: 44,
            padding: "0 20px",
            borderRadius: 12,
            background: "var(--accent)",
            color: "var(--accent-on)",
            fontSize: 14,
          }}
        >
          Расширить фильтры
        </button>
      </div>
    </div>
  );
}
