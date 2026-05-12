import { useEffect, useState } from "react";
import {
  adminBan,
  adminHidden,
  adminReports,
  adminRestore,
  adminStats,
  type AdminStats,
  type HiddenItem,
  type ReportItem,
} from "../api/client";
import { useStore } from "../store";

type Tab = "reports" | "hidden" | "stats";

export function AdminScreen() {
  const { setRoute } = useStore();
  const [tab, setTab] = useState<Tab>("reports");
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [hidden, setHidden] = useState<HiddenItem[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      if (tab === "reports") setReports(await adminReports());
      if (tab === "hidden") setHidden(await adminHidden());
      if (tab === "stats") setStats(await adminStats());
    } catch (e) {
      console.error("admin refresh", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function onRestore(id: string) {
    await adminRestore(id);
    await refresh();
  }
  async function onBan(id: string) {
    if (!confirm("Точно забанить навсегда?")) return;
    await adminBan(id);
    await refresh();
  }

  return (
    <div className="h-full overflow-y-auto pb-24">
      <div className="px-4 pt-2 pb-3">
        <div className="flex items-center justify-between mb-3">
          <h1
            className="font-display font-extrabold text-text"
            style={{ fontSize: 28, letterSpacing: "-0.04em" }}
          >
            Админка
          </h1>
          <button
            onClick={() => setRoute("settings")}
            className="text-text-2 font-display"
            style={{ fontSize: 13 }}
          >
            ← назад
          </button>
        </div>

        <div className="flex gap-1.5">
          {(["reports", "hidden", "stats"] as Tab[]).map((t) => (
            <TabBtn key={t} active={tab === t} onClick={() => setTab(t)}>
              {t === "reports" ? "Жалобы" : t === "hidden" ? "Скрытые" : "Статистика"}
            </TabBtn>
          ))}
        </div>
      </div>

      {loading && (
        <div className="px-4 py-6 text-center text-text-3 font-mono" style={{ fontSize: 11 }}>
          загружаю…
        </div>
      )}

      {!loading && tab === "reports" && (
        <div className="flex flex-col gap-2.5 px-4">
          {reports.length === 0 && (
            <Empty>пока никто не жалуется 🎉</Empty>
          )}
          {reports.map((r) => (
            <Card key={r.vacancy_id}>
              <Row>
                <strong className="text-text" style={{ fontSize: 14 }}>
                  {r.title}
                </strong>
                <span
                  style={{
                    background: "#3a1a1a",
                    color: "#ff8a8a",
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontSize: 11,
                  }}
                >
                  {r.reports_count}
                </span>
              </Row>
              <Sub>
                {r.company || "—"} · {r.city || "—"} · {r.source}
              </Sub>
              <Actions>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener"
                  style={btnSecondary}
                >
                  Открыть
                </a>
                <button onClick={() => onBan(r.vacancy_id)} style={btnDanger}>
                  🗑 Бан
                </button>
              </Actions>
            </Card>
          ))}
        </div>
      )}

      {!loading && tab === "hidden" && (
        <div className="flex flex-col gap-2.5 px-4">
          {hidden.length === 0 && <Empty>скрытых нет</Empty>}
          {hidden.map((h) => (
            <Card key={h.vacancy_id}>
              <Row>
                <strong className="text-text" style={{ fontSize: 14 }}>
                  {h.title}
                </strong>
                <span style={{ color: "#a8adb7", fontSize: 11 }}>
                  {h.reports_count} жалоб
                </span>
              </Row>
              <Sub>
                {h.company || "—"} · {h.source}
              </Sub>
              {h.hidden_reason && (
                <Sub style={{ color: "#ff8a8a" }}>{h.hidden_reason}</Sub>
              )}
              <Actions>
                <a href={h.url} target="_blank" rel="noopener" style={btnSecondary}>
                  Открыть
                </a>
                <button onClick={() => onRestore(h.vacancy_id)} style={btnPrimary}>
                  ✅ Восстановить
                </button>
                <button onClick={() => onBan(h.vacancy_id)} style={btnDanger}>
                  🗑 Бан
                </button>
              </Actions>
            </Card>
          ))}
        </div>
      )}

      {!loading && tab === "stats" && stats && (
        <div className="px-4 flex flex-col gap-2.5">
          <KV label="Юзеров всего" value={stats.users_total} />
          <KV label="Прошли онбординг" value={stats.users_onboarded} />
          <KV label="Активных за сутки" value={stats.users_dau} highlight />
          <KV label="Вакансий активных" value={stats.vacancies_active} highlight />
          <KV label="Скрытых модерацией" value={stats.vacancies_hidden} />
          <KV label="Помечено как спам" value={stats.vacancies_spam} />
          <KV label="Ожидают разбора жалоб" value={stats.reports_pending} />
          <KV label="Авто-скрытий за сутки" value={stats.autohides_today} />
          <Card>
            <Sub>По источникам</Sub>
            {Object.entries(stats.by_source).map(([k, v]) => (
              <Row key={k}>
                <span className="font-mono text-text-2" style={{ fontSize: 12 }}>
                  {k}
                </span>
                <span
                  className="font-mono text-text"
                  style={{ fontSize: 12 }}
                >
                  {v}
                </span>
              </Row>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}

const btnSecondary: React.CSSProperties = {
  padding: "8px 14px",
  borderRadius: 10,
  background: "#181B21",
  border: "1px solid #2A2F38",
  color: "var(--text)",
  fontSize: 12,
  fontWeight: 600,
  textDecoration: "none",
};
const btnPrimary: React.CSSProperties = {
  padding: "8px 14px",
  borderRadius: 10,
  background: "var(--accent)",
  color: "var(--accent-on)",
  fontSize: 12,
  fontWeight: 700,
  border: "none",
};
const btnDanger: React.CSSProperties = {
  padding: "8px 14px",
  borderRadius: 10,
  background: "#3a1a1a",
  color: "#ff8a8a",
  border: "1px solid #5a2a2a",
  fontSize: 12,
  fontWeight: 600,
};

function TabBtn({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="font-display font-semibold flex-1"
      style={{
        padding: "10px 14px",
        borderRadius: 12,
        background: active ? "var(--accent)" : "#181B21",
        color: active ? "var(--accent-on)" : "var(--text-2)",
        border: active ? "none" : "1px solid #2A2F38",
        fontSize: 13,
      }}
    >
      {children}
    </button>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        padding: 14,
        borderRadius: 14,
        background: "#181B21",
        border: "1px solid #2A2F38",
      }}
    >
      {children}
    </div>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-1.5 gap-2">{children}</div>
  );
}

function Sub({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className="text-text-2 font-display mb-1.5"
      style={{ fontSize: 12, ...style }}
    >
      {children}
    </div>
  );
}

function Actions({ children }: { children: React.ReactNode }) {
  return <div className="flex gap-1.5 mt-2 flex-wrap">{children}</div>;
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-center py-10 text-text-3 font-display"
      style={{ fontSize: 14 }}
    >
      {children}
    </div>
  );
}

function KV({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: 12,
        background: highlight ? "var(--accent)" : "#181B21",
        color: highlight ? "var(--accent-on)" : "var(--text)",
        border: highlight ? "none" : "1px solid #2A2F38",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
      }}
    >
      <span className="font-display" style={{ fontSize: 13, opacity: 0.8 }}>
        {label}
      </span>
      <span
        className="font-display font-extrabold"
        style={{ fontSize: 22, letterSpacing: "-0.03em" }}
      >
        {value}
      </span>
    </div>
  );
}
