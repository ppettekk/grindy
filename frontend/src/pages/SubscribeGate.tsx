import { useState } from "react";

interface Props {
  channel: string; // "@grindywork"
  onChecked: (subscribed: boolean) => void;
  recheck: () => Promise<boolean>;
}

export function SubscribeGate({ channel, onChecked, recheck }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handle = (channel || "@grindywork").replace(/^@/, "");
  const url = `https://t.me/${handle}`;

  async function onClickRecheck() {
    setLoading(true);
    setError(null);
    try {
      const ok = await recheck();
      if (ok) {
        onChecked(true);
      } else {
        setError("Не вижу подписки. Подпишись и нажми ещё раз.");
      }
    } catch {
      setError("Не удалось проверить. Попробуй ещё раз.");
    } finally {
      setLoading(false);
    }
  }

  function onClickSubscribe() {
    // В Telegram WebApp openTelegramLink работает в основном клиенте,
    // в desktop — открывает t.me ссылку.
    const tg = window.Telegram?.WebApp;
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url);
    } else {
      window.open(url, "_blank", "noopener");
    }
  }

  return (
    <div className="h-full flex flex-col items-center justify-center px-6 text-center bg-bg0">
      <div
        className="rounded-3xl p-8 max-w-sm w-full"
        style={{ background: "var(--bg1, #161618)" }}
      >
        <div
          className="text-5xl mb-4"
          aria-hidden
        >
          📣
        </div>
        <h1
          className="font-display font-extrabold text-text mb-3"
          style={{ fontSize: 26, letterSpacing: "-0.03em", lineHeight: 1.1 }}
        >
          Подпишись на наш канал
        </h1>
        <p
          className="text-text-2 mb-6"
          style={{ fontSize: 14, lineHeight: 1.5 }}
        >
          Чтобы пользоваться <b className="text-text">Grindy</b>, подпишись
          на <b className="text-text">@{handle}</b>. Там подборки вакансий,
          советы по подработке и анонсы новых фишек.
        </p>

        <button
          type="button"
          onClick={onClickSubscribe}
          className="w-full font-semibold rounded-2xl py-3.5 mb-3 transition-opacity active:opacity-80"
          style={{
            background: "var(--accent, #C7F751)",
            color: "var(--accent-fg, #0F0F10)",
            fontSize: 15,
          }}
        >
          📣 Подписаться
        </button>

        <button
          type="button"
          onClick={onClickRecheck}
          disabled={loading}
          className="w-full font-semibold rounded-2xl py-3.5 transition-opacity active:opacity-80"
          style={{
            background: "transparent",
            color: "var(--text, #fff)",
            border: "1px solid var(--text-3, #3a3a40)",
            fontSize: 15,
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? "Проверяю…" : "Я подписался"}
        </button>

        {error && (
          <p
            className="mt-4 text-text-2"
            style={{ fontSize: 13, color: "#ff8a8a" }}
          >
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
