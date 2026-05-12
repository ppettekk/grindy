import { useState } from "react";
import { useStore } from "../store";

const CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург"];

const CATEGORIES = [
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

type Step = "city" | "city_other" | "age" | "format" | "categories";

export function OnboardingScreen() {
  const { updateUser } = useStore();
  const [step, setStep] = useState<Step>("city");
  const [city, setCity] = useState<string>("");
  const [cityOther, setCityOther] = useState<string>("");
  const [age, setAge] = useState<14 | 16 | 18>(16);
  const [fmt, setFmt] = useState<"all" | "online" | "offline">("all");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  function pick(c: string) {
    const n = new Set(picked);
    if (n.has(c)) n.delete(c);
    else n.add(c);
    setPicked(n);
  }

  async function finish() {
    setSaving(true);
    const finalCity = step === "city_other" ? cityOther.trim() : city;
    try {
      await updateUser({
        city: finalCity || null,
        age_filter: age,
        format_filter: fmt,
        categories: [...picked],
        onboarded: true,
      });
    } finally {
      setSaving(false);
    }
  }

  const progress = (
    { city: 1, city_other: 1, age: 2, format: 3, categories: 4 } as Record<Step, number>
  )[step];

  return (
    <div className="h-full flex flex-col bg-bg0">
      <Header step={progress} total={4} />

      {step === "city" && (
        <Body
          title="Где ищем работу?"
          subtitle="Выбери город или введи свой"
        >
          <div className="grid grid-cols-2 gap-2">
            {CITIES.map((c) => (
              <Button
                key={c}
                onClick={() => {
                  setCity(c);
                  setStep("age");
                }}
                active={city === c}
              >
                {c}
              </Button>
            ))}
          </div>
          <button
            type="button"
            className="mt-3 w-full text-text-2 font-display"
            style={{ fontSize: 14, padding: 14 }}
            onClick={() => setStep("city_other")}
          >
            ✍️ Другой город
          </button>
        </Body>
      )}

      {step === "city_other" && (
        <Body title="Введи свой город" subtitle="Можно по-русски">
          <input
            value={cityOther}
            onChange={(e) => setCityOther(e.target.value)}
            placeholder="например, Краснодар"
            className="w-full bg-transparent outline-none text-text font-display"
            style={{
              fontSize: 18,
              padding: "16px 18px",
              borderRadius: 14,
              background: "#181B21",
              border: "1px solid #2A2F38",
            }}
          />
          <PrimaryButton
            onClick={() => {
              setCity(cityOther.trim() || "Москва");
              setStep("age");
            }}
            disabled={!cityOther.trim()}
          >
            Дальше
          </PrimaryButton>
        </Body>
      )}

      {step === "age" && (
        <Body title="Сколько тебе лет?" subtitle="Покажу подходящие вакансии">
          <div className="grid grid-cols-3 gap-2">
            {([14, 16, 18] as const).map((a) => (
              <Button
                key={a}
                active={age === a}
                onClick={() => {
                  setAge(a);
                  setStep("format");
                }}
              >
                {a}+
              </Button>
            ))}
          </div>
        </Body>
      )}

      {step === "format" && (
        <Body title="Формат работы?" subtitle="Можно потом поменять">
          <div className="flex flex-col gap-2">
            <Button
              active={fmt === "all"}
              onClick={() => {
                setFmt("all");
                setStep("categories");
              }}
            >
              И то и то
            </Button>
            <Button
              active={fmt === "offline"}
              onClick={() => {
                setFmt("offline");
                setStep("categories");
              }}
            >
              Офлайн
            </Button>
            <Button
              active={fmt === "online"}
              onClick={() => {
                setFmt("online");
                setStep("categories");
              }}
            >
              Онлайн
            </Button>
          </div>
        </Body>
      )}

      {step === "categories" && (
        <Body title="Что интересно?" subtitle="Выбери несколько или ничего">
          <div className="grid grid-cols-2 gap-2">
            {CATEGORIES.map((c) => {
              const on = picked.has(c);
              return (
                <Button key={c} active={on} onClick={() => pick(c)}>
                  {on ? "✓ " : ""}
                  {c}
                </Button>
              );
            })}
          </div>
          <PrimaryButton onClick={finish} disabled={saving}>
            {saving ? "Сохраняю…" : "🚀 Поехали"}
          </PrimaryButton>
        </Body>
      )}
    </div>
  );
}

function Header({ step, total }: { step: number; total: number }) {
  return (
    <div className="px-4 pt-3 pb-2">
      <div className="flex gap-1.5">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 3,
              borderRadius: 2,
              background: i < step ? "var(--accent)" : "#2A2F38",
            }}
          />
        ))}
      </div>
    </div>
  );
}

function Body({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 px-5 pt-6 overflow-y-auto pb-8">
      <h1
        className="font-display font-extrabold text-text mb-1"
        style={{ fontSize: 28, letterSpacing: "-0.04em", lineHeight: 1.05 }}
      >
        {title}
      </h1>
      <p className="text-text-2 mb-6 font-display" style={{ fontSize: 14 }}>
        {subtitle}
      </p>
      {children}
    </div>
  );
}

function Button({
  children,
  onClick,
  active,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-display font-semibold w-full"
      style={{
        padding: "16px 14px",
        borderRadius: 14,
        background: active ? "var(--accent)" : "#181B21",
        color: active ? "var(--accent-on)" : "var(--text)",
        border: active ? "none" : "1px solid #2A2F38",
        fontSize: 15,
      }}
    >
      {children}
    </button>
  );
}

function PrimaryButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="mt-6 w-full font-display font-bold"
      style={{
        padding: "16px",
        borderRadius: 14,
        background: "var(--accent)",
        color: "var(--accent-on)",
        opacity: disabled ? 0.5 : 1,
        fontSize: 16,
      }}
    >
      {children}
    </button>
  );
}
