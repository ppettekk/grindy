import { ArrowRight, Check, X } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Toggle } from "../components/Toggle";
import { tgUser, haptic } from "../lib/telegram";
import { useStore } from "../store";
import type { UserProfile } from "../types";

interface RowProps {
  label: string;
  sub?: string;
  right?: ReactNode;
  last?: boolean;
  onClick?: () => void;
}

function Row({ label, sub, right, last, onClick }: RowProps) {
  const Wrap = onClick ? "button" : "div";
  return (
    <Wrap
      onClick={onClick}
      className="w-full flex justify-between items-center px-4 py-3.5 text-left transition active:bg-bg2"
      style={{
        borderBottom: last ? "none" : "1px solid #2A2F38",
        background: "transparent",
        color: "inherit",
      }}
    >
      <div>
        <div
          className="font-display font-semibold text-text"
          style={{ fontSize: 14 }}
        >
          {label}
        </div>
        {sub && (
          <div className="text-text-3 mt-0.5" style={{ fontSize: 12 }}>
            {sub}
          </div>
        )}
      </div>
      {right}
    </Wrap>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div
      className="font-mono uppercase text-text-3 px-4"
      style={{
        fontSize: 10,
        letterSpacing: "0.08em",
        padding: "20px 16px 8px",
      }}
    >
      {children}
    </div>
  );
}

type EditField = null | "city" | "age" | "format" | "categories";

const ALL_CATEGORIES = [
  "Кафе и рестораны",
  "Промоутер",
  "Репетитор и обучение",
  "IT и интернет",
  "Дизайн и творчество",
  "Торговля и продажи",
  "Административная",
  "Доставка",
  "Другое",
];

export function SettingsScreen() {
  const { user, isAdmin, setRoute, updateUser } = useStore();
  const tgu = tgUser();
  const initial = (tgu?.first_name?.[0] || user?.first_name?.[0] || "?").toUpperCase();
  const [editing, setEditing] = useState<EditField>(null);

  const onToggle = (
    field: "notifications_morning" | "notifications_evening" | "notifications_realtime",
    val: boolean,
  ) => {
    haptic("light");
    updateUser({ [field]: val } as Partial<UserProfile>);
  };

  const fmtLabel = (f?: string) =>
    ({ all: "любой", online: "онлайн", offline: "офлайн" } as Record<string, string>)[f ?? "all"] ?? "—";

  return (
    <div className="h-full overflow-y-auto pb-24 relative">
      <div className="flex items-center gap-3.5 px-4 pt-2 pb-3">
        <div
          className="grid place-items-center font-display font-extrabold"
          style={{
            width: 64,
            height: 64,
            borderRadius: 32,
            background: "var(--accent)",
            color: "var(--accent-on)",
            fontSize: 26,
            letterSpacing: "-0.03em",
          }}
        >
          {initial}
        </div>
        <div>
          <div
            className="font-display font-extrabold text-text"
            style={{
              fontSize: 22,
              letterSpacing: "-0.03em",
            }}
          >
            {tgu?.first_name ?? user?.first_name ?? "Гость"}
            {user?.age_filter ? `, ${user.age_filter}` : ""}
          </div>
          <div className="text-text-3 font-mono" style={{ fontSize: 11 }}>
            {tgu?.username ? `@${tgu.username}` : "—"}
            {user?.city ? ` · ${user.city}` : ""}
          </div>
        </div>
      </div>

      <SectionLabel>Поиск</SectionLabel>
      <div
        className="mx-4 overflow-hidden"
        style={{
          background: "#111317",
          border: "1px solid #2A2F38",
          borderRadius: 14,
        }}
      >
        <Row
          label="Город"
          sub={user?.city || "не указан"}
          right={<ArrowRight size={16} color="#6E7480" />}
          onClick={() => setEditing("city")}
        />
        <Row
          label="Возраст"
          sub={user?.age_filter ? `${user.age_filter}+` : "не указан"}
          right={<ArrowRight size={16} color="#6E7480" />}
          onClick={() => setEditing("age")}
        />
        <Row
          label="Формат"
          sub={fmtLabel(user?.format_filter)}
          right={<ArrowRight size={16} color="#6E7480" />}
          onClick={() => setEditing("format")}
          last
        />
      </div>

      <SectionLabel>Категории</SectionLabel>
      <div
        className="mx-4 overflow-hidden"
        style={{
          background: "#111317",
          border: "1px solid #2A2F38",
          borderRadius: 14,
        }}
      >
        <Row
          label="Что интересно"
          sub={
            user?.categories && user.categories.length > 0
              ? user.categories.join(", ")
              : "все"
          }
          right={<ArrowRight size={16} color="#6E7480" />}
          onClick={() => setEditing("categories")}
          last
        />
      </div>

      <SectionLabel>Уведомления</SectionLabel>
      <div
        className="mx-4"
        style={{
          background: "#111317",
          border: "1px solid #2A2F38",
          borderRadius: 14,
        }}
      >
        <Row
          label="Утренняя подборка"
          sub="9:00 · топ-5 вакансий"
          right={
            <Toggle
              on={user?.notifications_morning ?? true}
              onChange={(v) => onToggle("notifications_morning", v)}
            />
          }
        />
        <Row
          label="Вечерняя подборка"
          sub="19:00 · топ-5 за день"
          right={
            <Toggle
              on={user?.notifications_evening ?? true}
              onChange={(v) => onToggle("notifications_evening", v)}
            />
          }
        />
        <Row
          label="Свежак сразу"
          sub="новые подходящие — каждые 30 мин"
          right={
            <Toggle
              on={user?.notifications_realtime ?? false}
              onChange={(v) => onToggle("notifications_realtime", v)}
            />
          }
          last
        />
      </div>

      {isAdmin && (
        <>
          <SectionLabel>Админка</SectionLabel>
          <div
            className="mx-4"
            style={{
              background: "#111317",
              border: "1px solid #2A2F38",
              borderRadius: 14,
            }}
          >
            <Row
              label="Жалобы и модерация"
              sub="разобрать жалобы / посмотреть статистику"
              right={<ArrowRight size={16} color="#6E7480" />}
              onClick={() => setRoute("admin")}
              last
            />
          </div>
        </>
      )}

      <SectionLabel>Поддержка</SectionLabel>
      <div
        className="mx-4 mb-4"
        style={{
          background: "#111317",
          border: "1px solid #2A2F38",
          borderRadius: 14,
        }}
      >
        <Row label="Помощь" right={<ArrowRight size={16} color="#6E7480" />} />
        <Row
          label="Связаться с нами"
          right={<ArrowRight size={16} color="#6E7480" />}
        />
        <Row
          label="О Grindy"
          sub="v0.1"
          right={<ArrowRight size={16} color="#6E7480" />}
          last
        />
      </div>

      <button
        onClick={() => setRoute("employers")}
        className="mx-4 mb-6 font-display"
        style={{
          width: "calc(100% - 32px)",
          height: 44,
          borderRadius: 12,
          background: "transparent",
          border: "1px solid #2A2F38",
          color: "#A8ADB7",
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        Я работодатель — разместить вакансию →
      </button>

      {editing && <EditSheet field={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function EditSheet({ field, onClose }: { field: EditField; onClose: () => void }) {
  const { user, updateUser } = useStore();
  const [city, setCity] = useState(user?.city ?? "");
  const [age, setAge] = useState<14 | 16 | 18>(
    (user?.age_filter as 14 | 16 | 18) ?? 16
  );
  const [fmt, setFmt] = useState<"all" | "online" | "offline">(
    (user?.format_filter as "all" | "online" | "offline") ?? "all"
  );
  const [picked, setPicked] = useState<Set<string>>(
    new Set(user?.categories ?? [])
  );

  const title = {
    city: "Город",
    age: "Возраст",
    format: "Формат работы",
    categories: "Категории",
  }[field as Exclude<EditField, null>];

  const apply = async () => {
    if (field === "city") await updateUser({ city: city.trim() || null });
    if (field === "age") await updateUser({ age_filter: age });
    if (field === "format") await updateUser({ format_filter: fmt });
    if (field === "categories") await updateUser({ categories: [...picked] });
    haptic("light");
    onClose();
  };

  const togglePicked = (c: string) => {
    const n = new Set(picked);
    if (n.has(c)) n.delete(c);
    else n.add(c);
    setPicked(n);
  };

  return (
    <div
      className="absolute inset-0 flex items-end z-10"
      style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={onClose}
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
            {title}
          </h2>
          <button
            onClick={onClose}
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

        {field === "city" && (
          <div>
            <input
              autoFocus
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Москва, СПб, Казань…"
              className="w-full font-display text-text bg-bg2 outline-none"
              style={{
                height: 48,
                padding: "0 14px",
                borderRadius: 12,
                border: "1px solid #2A2F38",
                fontSize: 15,
              }}
            />
            <div
              className="flex flex-wrap gap-1.5 mt-3"
              style={{ fontSize: 12 }}
            >
              {["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург"].map(
                (c) => (
                  <button
                    key={c}
                    onClick={() => setCity(c)}
                    className="font-display font-semibold"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 999,
                      background: "#181B21",
                      color: "#A8ADB7",
                      border: "1px solid #2A2F38",
                      fontSize: 12,
                    }}
                  >
                    {c}
                  </button>
                )
              )}
            </div>
          </div>
        )}

        {field === "age" && (
          <div
            className="flex gap-1.5 p-1"
            style={{ background: "#181B21", borderRadius: 12 }}
          >
            {[14, 16, 18].map((a) => {
              const on = age === a;
              return (
                <button
                  key={a}
                  onClick={() => setAge(a as 14 | 16 | 18)}
                  className="flex-1 font-display font-bold"
                  style={{
                    height: 44,
                    borderRadius: 9,
                    background: on ? "var(--accent)" : "transparent",
                    color: on ? "var(--accent-on)" : "#A8ADB7",
                    fontSize: 16,
                    border: "none",
                  }}
                >
                  {a}+
                </button>
              );
            })}
          </div>
        )}

        {field === "format" && (
          <div className="flex gap-1.5">
            {(
              [
                ["all", "Любой"],
                ["offline", "Офлайн"],
                ["online", "Онлайн"],
              ] as const
            ).map(([k, l]) => {
              const on = fmt === k;
              return (
                <button
                  key={k}
                  onClick={() => setFmt(k)}
                  className="flex-1 font-display font-semibold"
                  style={{
                    height: 44,
                    borderRadius: 12,
                    background: on ? "#F4F5F7" : "#181B21",
                    color: on ? "#0A0B0D" : "#A8ADB7",
                    border: `1px solid ${on ? "transparent" : "#2A2F38"}`,
                    fontSize: 14,
                  }}
                >
                  {l}
                </button>
              );
            })}
          </div>
        )}

        {field === "categories" && (
          <div className="flex flex-wrap gap-1.5">
            {ALL_CATEGORIES.map((c) => {
              const on = picked.has(c);
              return (
                <button
                  key={c}
                  onClick={() => togglePicked(c)}
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
        )}

        <button
          onClick={apply}
          className="mt-5 w-full font-display font-extrabold"
          style={{
            height: 50,
            borderRadius: 14,
            background: "var(--accent)",
            color: "var(--accent-on)",
            fontSize: 15,
            border: "none",
          }}
        >
          Сохранить
        </button>
      </div>
    </div>
  );
}
