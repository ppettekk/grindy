import { Home, Bookmark, User, type LucideIcon } from "lucide-react";
import type { Tab } from "../store";

interface Props {
  active: Tab;
  onChange: (t: Tab) => void;
}

const TABS: { id: Tab; icon: LucideIcon; label: string }[] = [
  { id: "feed", icon: Home, label: "Лента" },
  { id: "saved", icon: Bookmark, label: "Сохранено" },
  { id: "settings", icon: User, label: "Профиль" },
];

export function TabBar({ active, onChange }: Props) {
  return (
    <div
      className="absolute left-0 right-0 bottom-0 flex justify-around pt-2 pb-6"
      style={{
        background: "linear-gradient(180deg, transparent, #0A0B0D 30%)",
      }}
    >
      {TABS.map((t) => {
        const Icon = t.icon;
        const on = active === t.id;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className="flex flex-col items-center gap-1 px-3.5 py-1 font-display font-semibold"
            style={{
              fontSize: 10,
              color: on ? "var(--accent)" : "#6E7480",
            }}
          >
            <Icon
              size={22}
              color={on ? "var(--accent)" : "#6E7480"}
              fill={on ? "var(--accent)" : "none"}
            />
            <span>{t.label}</span>
          </button>
        );
      })}
    </div>
  );
}
