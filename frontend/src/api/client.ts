import type {
  Filters,
  SubscriptionStatus,
  UserProfile,
  Vacancy,
  VacancyList,
} from "../types";
import { getInitData } from "../lib/telegram";

const BASE = (import.meta.env.VITE_API_BASE as string) || "";

async function http<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const initData = getInitData();
  if (initData) headers.set("X-Telegram-Init-Data", initData);

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = body.detail || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

export function listVacancies(
  filters: Partial<Filters> & { cursor?: string | null; limit?: number }
): Promise<VacancyList> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.city) params.set("city", filters.city);
  if (filters.age) params.set("age", String(filters.age));
  if (filters.format && filters.format !== "all") params.set("format", filters.format);
  if (filters.salary_from && filters.salary_from > 0)
    params.set("salary_from", String(filters.salary_from));
  for (const c of filters.categories ?? []) params.append("categories", c);
  if (filters.cursor) params.set("cursor", filters.cursor);
  if (filters.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return http<VacancyList>(`/api/vacancies${qs ? `?${qs}` : ""}`);
}

export function getVacancy(id: string): Promise<Vacancy> {
  return http<Vacancy>(`/api/vacancies/${id}`);
}

export function reportVacancy(id: string, reason?: string): Promise<void> {
  return http<void>(`/api/vacancies/${id}/report`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
  });
}

export function upsertUser(payload: {
  telegram_id: number;
  username?: string;
  first_name?: string;
  city?: string;
  age_filter?: number;
  format_filter?: "all" | "online" | "offline";
  categories?: string[];
}): Promise<UserProfile> {
  return http<UserProfile>("/api/users", {
    method: "POST",
    body: JSON.stringify({
      age_filter: 16,
      format_filter: "all",
      categories: [],
      ...payload,
    }),
  });
}

export function getUser(telegramId: number): Promise<UserProfile> {
  return http<UserProfile>(`/api/users/${telegramId}`);
}

export function patchUser(
  telegramId: number,
  patch: Partial<UserProfile>
): Promise<UserProfile> {
  return http<UserProfile>(`/api/users/${telegramId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

// ── Подписка на канал ───────────────────────────────────────────────

export function getSubscription(telegramId: number): Promise<SubscriptionStatus> {
  return http<SubscriptionStatus>(`/api/users/${telegramId}/subscription`);
}

// ── Saved vacancies ─────────────────────────────────────────────────

export function listSaved(telegramId: number): Promise<VacancyList> {
  return http<VacancyList>(`/api/users/${telegramId}/saved`);
}

export function saveVacancy(
  telegramId: number,
  vacancyId: string
): Promise<{ ok: boolean }> {
  return http(`/api/users/${telegramId}/saved/${vacancyId}`, {
    method: "POST",
  });
}

export function unsaveVacancy(
  telegramId: number,
  vacancyId: string
): Promise<{ ok: boolean }> {
  return http(`/api/users/${telegramId}/saved/${vacancyId}`, {
    method: "DELETE",
  });
}

// ── Admin ───────────────────────────────────────────────────────────

export interface AdminMe {
  is_admin: boolean;
  telegram_id: number;
}

export interface ReportItem {
  vacancy_id: string;
  reports_count: number;
  last_report_at: string;
  title: string;
  company: string | null;
  city: string | null;
  source: string;
  url: string;
  is_hidden: boolean;
}

export interface HiddenItem {
  vacancy_id: string;
  title: string;
  company: string | null;
  source: string;
  url: string;
  hidden_reason: string | null;
  reports_count: number;
}

export interface AdminStats {
  users_total: number;
  users_dau: number;
  users_onboarded: number;
  vacancies_total: number;
  vacancies_active: number;
  vacancies_hidden: number;
  vacancies_spam: number;
  by_source: Record<string, number>;
  reports_pending: number;
  autohides_today: number;
}

export async function adminCheck(): Promise<boolean> {
  try {
    const r = await http<AdminMe>("/api/admin/me");
    return r.is_admin;
  } catch {
    return false;
  }
}

export function adminReports(): Promise<ReportItem[]> {
  return http<ReportItem[]>("/api/admin/reports");
}

export function adminHidden(): Promise<HiddenItem[]> {
  return http<HiddenItem[]>("/api/admin/hidden");
}

export function adminStats(): Promise<AdminStats> {
  return http<AdminStats>("/api/admin/stats");
}

export function adminRestore(vacancyId: string): Promise<{ ok: boolean }> {
  return http(`/api/admin/vacancies/${vacancyId}/restore`, { method: "POST" });
}

export function adminBan(vacancyId: string): Promise<{ ok: boolean }> {
  return http(`/api/admin/vacancies/${vacancyId}/ban`, { method: "POST" });
}
