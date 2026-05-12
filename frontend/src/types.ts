export type Source = "hh" | "avito" | "superjob" | "rabota" | "direct";
export type Format = "online" | "offline" | "hybrid";

export interface Vacancy {
  id: string;
  source: Source;
  title: string;
  company?: string | null;
  description?: string | null;
  salary_from?: number | null;
  salary_to?: number | null;
  salary_unit?: string | null;
  city?: string | null;
  format: Format;
  category?: string | null;
  min_age: number;
  url: string;
  is_direct: boolean;
  is_verified: boolean;
  is_featured: boolean;
  is_suspect: boolean;
  spam_reason?: string | null;
  posted_at?: string | null;
  created_at: string;
}

export interface VacancyList {
  items: Vacancy[];
  next_cursor: string | null;
  total: number;
}

export interface Filters {
  q: string;
  city: string;
  age: 14 | 16 | 18 | null;
  format: "all" | "online" | "offline";
  salary_from: number;
  categories: string[];
}

export interface UserProfile {
  id: string;
  telegram_id: number;
  username?: string | null;
  first_name?: string | null;
  city?: string | null;
  age_filter: number;
  format_filter: "all" | "online" | "offline";
  categories: string[];
  notifications_morning: boolean;
  notifications_evening: boolean;
  notifications_realtime: boolean;
  onboarded: boolean;
}

export interface SubscriptionStatus {
  required: boolean;
  subscribed: boolean;
  channel: string | null;
}
