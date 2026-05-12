import { useEffect, useState } from "react";
import { useStore } from "./store";
import { initTelegram, tgUser } from "./lib/telegram";
import { adminCheck, getSubscription, upsertUser } from "./api/client";

import { FeedScreen } from "./pages/FeedScreen";
import { DetailScreen } from "./pages/DetailScreen";
import { FiltersScreen } from "./pages/FiltersScreen";
import { SavedScreen } from "./pages/SavedScreen";
import { SettingsScreen } from "./pages/SettingsScreen";
import { EmptyScreen } from "./pages/EmptyScreen";
import { EmployerPage } from "./pages/EmployerPage";
import { SubscribeGate } from "./pages/SubscribeGate";
import { OnboardingScreen } from "./pages/OnboardingScreen";
import { AdminScreen } from "./pages/AdminScreen";
import { TabBar } from "./components/TabBar";

type SubState =
  | { kind: "loading" }
  | { kind: "ok" }
  | { kind: "blocked"; channel: string };

export default function App() {
  const {
    route,
    tab,
    user,
    openedVacancy,
    setTab,
    loadInitial,
    setUser,
    setIsAdmin,
    setFilters,
    loadSaved,
  } = useStore();

  const [sub, setSub] = useState<SubState>({ kind: "loading" });

  async function bootstrapProfile() {
    const u = tgUser();
    if (!u?.id) {
      loadInitial();
      return;
    }
    try {
      const profile = await upsertUser({
        telegram_id: u.id,
        username: u.username,
        first_name: u.first_name,
      });
      setUser(profile);
      loadSaved();
      setFilters({
        city: profile.city ?? "",
        age:
          profile.age_filter === 14 || profile.age_filter === 16 || profile.age_filter === 18
            ? (profile.age_filter as 14 | 16 | 18)
            : null,
        format: (profile.format_filter as "all" | "online" | "offline") ?? "all",
        categories: profile.categories ?? [],
      });
      // Параллельно — проверка админа
      adminCheck().then(setIsAdmin).catch(() => setIsAdmin(false));
    } catch (e) {
      console.error("upsertUser", e);
    }
    loadInitial();
  }

  useEffect(() => {
    initTelegram();
    const u = tgUser();

    (async () => {
      // 1) Проверка подписки на канал
      if (u?.id) {
        try {
          const s = await getSubscription(u.id);
          if (s.required && !s.subscribed) {
            setSub({ kind: "blocked", channel: s.channel ?? "@grindywork" });
            return;
          }
        } catch (e) {
          console.warn("subscription check failed", e);
        }
      }
      setSub({ kind: "ok" });
      bootstrapProfile();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function recheckSubscription(): Promise<boolean> {
    const u = tgUser();
    if (!u?.id) return true;
    const s = await getSubscription(u.id);
    return !s.required || s.subscribed;
  }

  if (sub.kind === "loading") {
    return (
      <div className="h-full flex items-center justify-center bg-bg0">
        <div className="text-text-2 font-display" style={{ fontSize: 14 }}>
          Загрузка…
        </div>
      </div>
    );
  }

  if (sub.kind === "blocked") {
    return (
      <SubscribeGate
        channel={sub.channel}
        recheck={recheckSubscription}
        onChecked={(ok) => {
          if (ok) {
            setSub({ kind: "ok" });
            bootstrapProfile();
          }
        }}
      />
    );
  }

  // First-run onboarding в WebApp.
  // Показываем, если профиль уже подгружен и user.onboarded === false.
  if (user && !user.onboarded) {
    return (
      <div className="relative h-full max-w-[480px] mx-auto bg-bg0">
        <OnboardingScreen />
      </div>
    );
  }

  if (route === "employers") {
    return <EmployerPage />;
  }

  return (
    <div className="relative h-full max-w-[480px] mx-auto bg-bg0">
      {route === "feed" && <FeedScreen />}
      {route === "saved" && <SavedScreen />}
      {route === "settings" && <SettingsScreen />}
      {route === "empty" && <EmptyScreen />}
      {route === "admin" && <AdminScreen />}
      {route === "detail" && openedVacancy && <DetailScreen v={openedVacancy} />}
      {route === "filters" && (
        <>
          <FeedScreen />
          <FiltersScreen />
        </>
      )}
      {route !== "detail" && route !== "filters" && route !== "admin" && (
        <TabBar active={tab} onChange={setTab} />
      )}
    </div>
  );
}
