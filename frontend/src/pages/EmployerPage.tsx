import { useState } from "react";
import { ArrowRight, Check, ShieldCheck } from "lucide-react";
import { GrindyWordmark } from "../components/Logo";
import { useStore } from "../store";

const PLANS = [
  {
    key: "basic",
    name: "Базовый",
    price: "500",
    per: "/ 30 дней",
    tag: "старт",
    feats: [
      "Вакансия в общей ленте",
      "Карточка с зарплатой и контактами",
      "AI-модерация",
      "Статистика просмотров",
    ],
    cta: "Разместить",
    highlight: false,
  },
  {
    key: "featured",
    name: "Закреп",
    price: "1 500",
    per: "/ 30 дней",
    tag: "хит",
    feats: [
      "Всё из базового",
      "📌 Закреп вверху ленты",
      "Метка в утренней подборке",
      "В 5× больше откликов",
    ],
    cta: "Закрепить",
    highlight: true,
  },
  {
    key: "verified",
    name: "Verified",
    price: "3 000",
    per: "/ 3 месяца",
    tag: "для брендов",
    feats: [
      "Значок ◆ verified навсегда",
      "Безлимит вакансий 3 месяца",
      "Промо в ТГ-канале (1 пост)",
      "Менеджер",
    ],
    cta: "Стать партнёром",
    highlight: false,
  },
];

export function EmployerPage() {
  const { setRoute } = useStore();
  const [selectedPlan, setSelectedPlan] = useState("featured");

  return (
    <div className="min-h-screen w-full bg-bg0 text-text font-display">
      <div className="max-w-[1200px] mx-auto" style={{ padding: 56 }}>
        {/* nav */}
        <div className="flex justify-between items-center mb-16">
          <button onClick={() => setRoute("feed")}>
            <GrindyWordmark size={24} />
          </button>
          <div
            className="hidden md:flex gap-7 items-center"
            style={{ color: "#A8ADB7", fontSize: 14, fontWeight: 500 }}
          >
            <span>Для подростков</span>
            <span style={{ color: "#F4F5F7" }}>Работодателям</span>
            <span>Канал</span>
            <button
              className="font-bold"
              style={{
                background: "var(--accent)",
                color: "var(--accent-on)",
                padding: "10px 18px",
                borderRadius: 12,
                fontSize: 14,
              }}
            >
              Разместить вакансию
            </button>
          </div>
        </div>

        {/* hero */}
        <div
          className="grid gap-10 lg:grid-cols-[1.2fr_1fr] items-center mb-20"
          style={{ gap: 60 }}
        >
          <div>
            <div
              className="inline-flex items-center gap-1.5 mb-6 font-mono"
              style={{
                padding: "6px 12px",
                background: "#181B21",
                borderRadius: 999,
                color: "#A8ADB7",
                fontSize: 11,
                letterSpacing: "0.04em",
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  background: "var(--accent)",
                }}
              />
              12 400+ подростков уже в Grindy
            </div>
            <h1
              className="font-extrabold mb-6"
              style={{
                fontSize: "clamp(48px, 8vw, 84px)",
                letterSpacing: "-0.04em",
                lineHeight: 0.95,
                margin: "0 0 24px",
              }}
            >
              Найди
              <br />
              <span style={{ color: "var(--accent)" }}>джунов,</span>
              <br />
              пока они в школе.
            </h1>
            <p
              className="text-text-2 mb-8 max-w-[480px]"
              style={{ fontSize: 18, lineHeight: 1.5 }}
            >
              Размещение вакансий для подростков 14–18 лет в Telegram. Аудитория, до которой не дотягивается hh.
            </p>
            <div className="flex gap-3 flex-wrap">
              <button
                className="font-extrabold inline-flex items-center gap-2"
                style={{
                  background: "var(--accent)",
                  color: "var(--accent-on)",
                  padding: "16px 28px",
                  borderRadius: 14,
                  fontSize: 16,
                }}
              >
                Разместить за 5 минут <ArrowRight size={18} />
              </button>
              <button
                className="font-semibold"
                style={{
                  background: "transparent",
                  color: "#F4F5F7",
                  border: "1px solid #2A2F38",
                  padding: "16px 24px",
                  borderRadius: 14,
                  fontSize: 16,
                }}
              >
                Тарифы ↓
              </button>
            </div>
          </div>

          {/* stats card */}
          <div
            style={{
              background: "#111317",
              border: "1px solid #2A2F38",
              borderRadius: 24,
              padding: 28,
            }}
          >
            <div
              className="font-mono uppercase mb-6"
              style={{
                fontSize: 11,
                letterSpacing: "0.08em",
                color: "#6E7480",
              }}
            >
              Аудитория Grindy
            </div>
            <div className="grid grid-cols-2 gap-6">
              {[
                ["12 400+", "подписчиков"],
                ["68%", "14–17 лет"],
                ["9:00 / 19:00", "пуш утром и вечером"],
                ["72%", "открывают подборки"],
              ].map(([n, l], i) => (
                <div key={i}>
                  <div
                    className="font-extrabold"
                    style={{
                      fontSize: 36,
                      letterSpacing: "-0.03em",
                      lineHeight: 1,
                      color: i % 3 === 0 ? "var(--accent)" : "#F4F5F7",
                    }}
                  >
                    {n}
                  </div>
                  <div
                    className="mt-1.5 text-text-3"
                    style={{ fontSize: 13 }}
                  >
                    {l}
                  </div>
                </div>
              ))}
            </div>
            <div
              style={{
                height: 1,
                background: "#2A2F38",
                margin: "24px 0",
              }}
            />
            <div className="flex items-center gap-2.5">
              <ShieldCheck size={16} color="#3DDC97" />
              <span className="text-text-2" style={{ fontSize: 13 }}>
                Каждая вакансия проходит AI-модерацию на спам
              </span>
            </div>
          </div>
        </div>

        {/* pricing */}
        <div className="mb-6">
          <div
            className="font-mono uppercase mb-2"
            style={{
              fontSize: 11,
              letterSpacing: "0.08em",
              color: "#6E7480",
            }}
          >
            Тарифы
          </div>
          <h2
            className="font-extrabold"
            style={{
              fontSize: "clamp(32px, 5vw, 48px)",
              letterSpacing: "-0.04em",
              margin: "0 0 36px",
            }}
          >
            Платишь только за результат
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PLANS.map((p) => (
            <div
              key={p.key}
              onClick={() => setSelectedPlan(p.key)}
              className="cursor-pointer transition"
              style={{
                background: p.highlight ? "var(--accent)" : "#111317",
                color: p.highlight ? "var(--accent-on)" : "#F4F5F7",
                border: `1px solid ${p.highlight ? "transparent" : "#2A2F38"}`,
                borderRadius: 24,
                padding: 28,
                outline:
                  selectedPlan === p.key && !p.highlight
                    ? "2px solid var(--accent)"
                    : undefined,
              }}
            >
              <div className="flex justify-between items-center mb-6">
                <span
                  className="font-extrabold"
                  style={{ fontSize: 22, letterSpacing: "-0.03em" }}
                >
                  {p.name}
                </span>
                <span
                  className="font-mono uppercase"
                  style={{
                    fontSize: 10,
                    letterSpacing: "0.06em",
                    padding: "4px 8px",
                    borderRadius: 6,
                    background: p.highlight ? "rgba(0,0,0,0.15)" : "#23272F",
                    color: p.highlight ? "var(--accent-on)" : "#A8ADB7",
                  }}
                >
                  {p.tag}
                </span>
              </div>
              <div className="mb-6">
                <span
                  className="font-extrabold"
                  style={{
                    fontSize: 56,
                    letterSpacing: "-0.04em",
                    lineHeight: 1,
                  }}
                >
                  {p.price}
                </span>
                <span
                  className="font-bold"
                  style={{ fontSize: 22, opacity: 0.6 }}
                >
                  {" "}
                  ₽
                </span>
                <div style={{ fontSize: 13, opacity: 0.65, marginTop: 4 }}>
                  {p.per}
                </div>
              </div>
              <ul className="list-none p-0 mb-7 flex flex-col gap-2.5">
                {p.feats.map((f, k) => (
                  <li
                    key={k}
                    className="flex items-center gap-2.5"
                    style={{ fontSize: 14 }}
                  >
                    <Check
                      size={14}
                      color={p.highlight ? "var(--accent-on)" : "var(--accent)"}
                    />
                    <span style={{ opacity: p.highlight ? 0.85 : 1 }}>{f}</span>
                  </li>
                ))}
              </ul>
              <button
                className="w-full font-extrabold"
                style={{
                  padding: "14px",
                  borderRadius: 12,
                  background: p.highlight ? "var(--accent-on)" : "var(--accent)",
                  color: p.highlight ? "var(--accent)" : "var(--accent-on)",
                  fontSize: 14,
                }}
              >
                {p.cta}
              </button>
            </div>
          ))}
        </div>

        {/* form */}
        <EmployerForm planKey={selectedPlan} />
      </div>
    </div>
  );
}

function EmployerForm({ planKey }: { planKey: string }) {
  const price = planKey === "verified" ? "3 000" : planKey === "basic" ? "500" : "1 500";
  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-10"
      style={{
        marginTop: 56,
        padding: 36,
        background: "#111317",
        border: "1px solid #2A2F38",
        borderRadius: 24,
      }}
    >
      <div>
        <div
          className="font-mono uppercase mb-3"
          style={{
            fontSize: 11,
            letterSpacing: "0.08em",
            color: "#6E7480",
          }}
        >
          Шаг 1 / 1
        </div>
        <h2
          className="font-extrabold mb-4"
          style={{
            fontSize: 36,
            letterSpacing: "-0.03em",
            margin: "0 0 16px",
            lineHeight: 1.05,
          }}
        >
          Опубликуй
          <br />
          вакансию
        </h2>
        <p className="text-text-2 m-0" style={{ fontSize: 14, lineHeight: 1.5 }}>
          Заполни форму — модерация и публикация в ленте за 15 минут. Оплата ЮКассой.
        </p>
      </div>
      <form className="flex flex-col gap-3" onSubmit={(e) => e.preventDefault()}>
        {(
          [
            ["Название вакансии", "Бариста на выходные"],
            ["Компания", "Surf Coffee"],
            ["Город / адрес", "Москва, м. Чистые Пруды"],
          ] as const
        ).map(([l, ph]) => (
          <Field key={l} label={l} placeholder={ph} />
        ))}
        <div className="grid grid-cols-3 gap-2">
          <Field label="Возраст" placeholder="16+" small />
          <Field label="Зарплата от" placeholder="350 ₽/час" small />
          <Field label="Формат" placeholder="офлайн" small />
        </div>
        <button
          className="font-extrabold flex items-center justify-center gap-2"
          style={{
            marginTop: 8,
            height: 56,
            borderRadius: 14,
            background: "var(--accent)",
            color: "var(--accent-on)",
            fontSize: 16,
          }}
        >
          Перейти к оплате · {price} ₽ <ArrowRight size={18} />
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  placeholder,
  small,
}: {
  label: string;
  placeholder: string;
  small?: boolean;
}) {
  return (
    <div>
      <div
        className="font-mono uppercase mb-1.5 text-text-3"
        style={{ fontSize: 10, letterSpacing: "0.08em" }}
      >
        {label}
      </div>
      <input
        placeholder={placeholder}
        className="w-full bg-bg2 border outline-none text-text"
        style={{
          height: 48,
          padding: small ? "0 14px" : "0 16px",
          borderColor: "#2A2F38",
          borderRadius: 12,
          fontSize: small ? 13 : 14,
        }}
      />
    </div>
  );
}
