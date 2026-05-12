/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    Telegram?: {
      WebApp?: any;
    };
  }
}

export const tg = (): any | undefined => window.Telegram?.WebApp;

export function initTelegram(): void {
  const w = tg();
  if (!w) return;
  try {
    w.ready();
    w.expand();
    w.setHeaderColor("#0A0B0D");
    w.setBackgroundColor("#0A0B0D");
  } catch {
    // ignore
  }
}

export function getInitData(): string {
  return tg()?.initData ?? "";
}

export function tgUser():
  | { id: number; username?: string; first_name?: string }
  | undefined {
  return tg()?.initDataUnsafe?.user;
}

/** start_param из Telegram deep link (?startapp=...). Полезен для открытия
 *  конкретной вакансии из пуш-уведомления бота. */
export function tgStartParam(): string | undefined {
  const p = tg()?.initDataUnsafe?.start_param;
  return typeof p === "string" && p ? p : undefined;
}

export function haptic(kind: "light" | "medium" | "heavy" | "rigid" | "soft" = "light"): void {
  try {
    tg()?.HapticFeedback?.impactOccurred(kind);
  } catch {
    // ignore
  }
}

export function setBackButton(handler?: () => void): void {
  const bb = tg()?.BackButton;
  if (!bb) return;
  if (handler) {
    bb.show();
    bb.onClick(handler);
  } else {
    bb.hide();
    bb.offClick();
  }
}
