import { create } from "zustand";
import type { Filters, UserProfile, Vacancy } from "../types";
import * as api from "../api/client";
import { tgUser } from "../lib/telegram";

export type Route =
  | "feed"
  | "detail"
  | "filters"
  | "saved"
  | "settings"
  | "empty"
  | "employers"
  | "onboarding"
  | "admin";
export type Tab = "feed" | "saved" | "settings";

interface State {
  route: Route;
  tab: Tab;
  user: UserProfile | null;
  isAdmin: boolean;
  vacancies: Vacancy[];
  cursor: string | null;
  loading: boolean;
  total: number;
  filters: Filters;
  query: string;
  saved: Set<string>;
  savedVacancies: Vacancy[];
  viewed: Set<string>;
  openedVacancy: Vacancy | null;

  setRoute: (r: Route) => void;
  setTab: (t: Tab) => void;
  setQuery: (q: string) => void;
  setFilters: (f: Partial<Filters>) => void;
  resetFilters: () => void;
  toggleCategory: (c: string) => void;
  toggleSaved: (id: string) => void;
  markViewed: (id: string) => void;

  setUser: (u: UserProfile | null) => void;
  setIsAdmin: (v: boolean) => void;
  updateUser: (patch: Partial<UserProfile>) => Promise<void>;

  loadSaved: () => Promise<void>;

  loadInitial: () => Promise<void>;
  loadMore: () => Promise<void>;
  openVacancy: (v: Vacancy) => void;
  closeVacancy: () => void;
}

const DEFAULT_FILTERS: Filters = {
  q: "",
  city: "",
  age: null,
  format: "all",
  salary_from: 0,
  categories: [],
};

const VIEWED_KEY = "grindy.viewed";
const VIEWED_LIMIT = 500; // Не разрастаем localStorage бесконечно.

function loadViewed(): Set<string> {
  try {
    const arr = JSON.parse(localStorage.getItem(VIEWED_KEY) ?? "[]");
    if (Array.isArray(arr)) return new Set(arr);
  } catch {
    /* empty */
  }
  return new Set();
}

function persistViewed(s: Set<string>) {
  try {
    // Ограничим размер - выкидываем самые старые при переполнении.
    const arr = [...s];
    const trimmed = arr.length > VIEWED_LIMIT ? arr.slice(-VIEWED_LIMIT) : arr;
    localStorage.setItem(VIEWED_KEY, JSON.stringify(trimmed));
  } catch {
    /* empty */
  }
}

export const useStore = create<State>((set, get) => ({
  route: "feed",
  tab: "feed",
  user: null,
  isAdmin: false,
  vacancies: [],
  cursor: null,
  loading: false,
  total: 0,
  filters: { ...DEFAULT_FILTERS },
  query: "",
  saved: new Set<string>(),
  savedVacancies: [],
  viewed: loadViewed(),
  openedVacancy: null,

  setRoute: (route) => set({ route }),
  setTab: (tab) => {
    const route: Route = tab === "feed" ? "feed" : tab === "saved" ? "saved" : "settings";
    set({ tab, route });
  },
  setQuery: (q) => {
    set({ query: q, filters: { ...get().filters, q } });
  },
  setFilters: (f) => set({ filters: { ...get().filters, ...f } }),
  resetFilters: () => set({ filters: { ...DEFAULT_FILTERS, q: get().query } }),
  toggleCategory: (c) => {
    const { categories } = get().filters;
    const next = categories.includes(c)
      ? categories.filter((x) => x !== c)
      : [...categories, c];
    set({ filters: { ...get().filters, categories: next } });
  },
  toggleSaved: (id) => {
    const next = new Set(get().saved);
    const wasSaved = next.has(id);
    if (wasSaved) next.delete(id);
    else next.add(id);
    set({ saved: next });
    try {
      localStorage.setItem("grindy.saved", JSON.stringify([...next]));
    } catch {
      /* empty */
    }

    const tg = tgUser();
    if (tg?.id) {
      const fn = wasSaved ? api.unsaveVacancy : api.saveVacancy;
      fn(tg.id, id).catch((e) => {
        console.error("toggleSaved sync failed", e);
        const rb = new Set(get().saved);
        if (wasSaved) rb.add(id);
        else rb.delete(id);
        set({ saved: rb });
      });

      if (wasSaved) {
        set({
          savedVacancies: get().savedVacancies.filter((v) => v.id !== id),
        });
      }
    }
  },

  markViewed: (id) => {
    const cur = get().viewed;
    if (cur.has(id)) return;
    const next = new Set(cur);
    next.add(id);
    set({ viewed: next });
    persistViewed(next);
  },

  loadInitial: async () => {
    set({ loading: true });
    try {
      const restored = JSON.parse(localStorage.getItem("grindy.saved") ?? "[]");
      if (Array.isArray(restored)) set({ saved: new Set(restored) });
    } catch {
      /* empty */
    }
    try {
      const r = await api.listVacancies({ ...get().filters, limit: 20 });
      set({
        vacancies: r.items,
        cursor: r.next_cursor,
        total: r.total,
        loading: false,
        route: r.items.length === 0 ? "empty" : "feed",
      });
    } catch (e) {
      console.error(e);
      set({ loading: false });
    }
  },

  loadMore: async () => {
    if (get().loading || !get().cursor) return;
    set({ loading: true });
    try {
      const r = await api.listVacancies({
        ...get().filters,
        cursor: get().cursor!,
        limit: 20,
      });
      set({
        vacancies: [...get().vacancies, ...r.items],
        cursor: r.next_cursor,
        total: r.total,
        loading: false,
      });
    } catch (e) {
      console.error(e);
      set({ loading: false });
    }
  },

  openVacancy: (v) => {
    get().markViewed(v.id);
    set({ openedVacancy: v, route: "detail" });
  },
  closeVacancy: () => set({ openedVacancy: null, route: "feed" }),

  loadSaved: async () => {
    const tg = tgUser();
    if (!tg?.id) return;
    try {
      const r = await api.listSaved(tg.id);
      const ids = r.items.map((v) => v.id);
      set({
        savedVacancies: r.items,
        saved: new Set(ids),
      });
      try {
        localStorage.setItem("grindy.saved", JSON.stringify(ids));
      } catch {
        /* empty */
      }
    } catch (e) {
      console.error("loadSaved", e);
    }
  },

  setUser: (user) => set({ user }),
  setIsAdmin: (v) => set({ isAdmin: v }),

  updateUser: async (patch) => {
    const cur = get().user;
    if (!cur) return;
    const next: UserProfile = { ...cur, ...patch } as UserProfile;
    set({ user: next });
    try {
      const saved = await api.patchUser(cur.telegram_id, patch);
      set({ user: saved });
      if (
        patch.city !== undefined ||
        patch.age_filter !== undefined ||
        patch.format_filter !== undefined ||
        patch.categories !== undefined
      ) {
        const f = get().filters;
        set({
          filters: {
            ...f,
            city: saved.city ?? f.city,
            age: (saved.age_filter as 14 | 16 | 18 | undefined) ?? f.age,
            format: saved.format_filter ?? f.format,
            categories: saved.categories ?? f.categories,
          },
        });
        get().loadInitial();
      }
    } catch (e) {
      console.error("updateUser", e);
      set({ user: cur });
    }
  },
}));
