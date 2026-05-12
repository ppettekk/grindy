import type { Vacancy } from "../types";

export function formatSalary(v: Vacancy): string {
  if (!v.salary_from && !v.salary_to) return "не указана";
  const fmt = (n: number) => n.toLocaleString("ru-RU");
  if (v.salary_from && v.salary_to) {
    return `${fmt(v.salary_from)}–${fmt(v.salary_to)}`;
  }
  if (v.salary_from) return `от ${fmt(v.salary_from)}`;
  return `до ${fmt(v.salary_to ?? 0)}`;
}

export function formatPosted(dt: string | null | undefined): string {
  if (!dt) return "";
  try {
    const d = new Date(dt);
    const diff = Date.now() - d.getTime();
    const min = Math.floor(diff / 60_000);
    if (min < 60) return `${min} мин назад`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr} ч назад`;
    const days = Math.floor(hr / 24);
    if (days < 7) return `${days} д назад`;
    return d.toLocaleDateString("ru-RU");
  } catch {
    return "";
  }
}

export const SOURCE_LABEL: Record<string, string> = {
  hh: "hh",
  avito: "avito",
  superjob: "sj",
  rabota: "r.ru",
  direct: "◆ direct",
};

export function fmtLabel(f: string): string {
  return ({ online: "онлайн", offline: "офлайн", hybrid: "гибрид" } as Record<
    string,
    string
  >)[f] ?? f;
}
