import { useEffect } from "react";
import { VacancyCard } from "../components/VacancyCard";
import { useStore } from "../store";

export function SavedScreen() {
  const { savedVacancies, openVacancy, loadSaved } = useStore();

  useEffect(() => {
    loadSaved();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-full overflow-y-auto pb-24">
      <div className="px-4 pt-2 pb-4">
        <h1
          className="font-display font-extrabold text-text mb-1"
          style={{
            fontSize: 32,
            letterSpacing: "-0.04em",
            margin: "8px 0 4px",
          }}
        >
          Сохранённые
        </h1>
        <p className="text-text-3 m-0" style={{ fontSize: 13 }}>
          {savedVacancies.length} {plural(savedVacancies.length)} — никуда не убегут
        </p>
      </div>
      <div className="flex flex-col gap-2.5 px-4">
        {savedVacancies.length === 0 && (
          <div
            className="text-center py-10 text-text-2 font-display"
            style={{ fontSize: 14 }}
          >
            Сохрани понравившиеся вакансии — они появятся здесь.
          </div>
        )}
        {savedVacancies.map((v) => (
          <VacancyCard key={v.id} v={v} onOpen={() => openVacancy(v)} />
        ))}
      </div>
    </div>
  );
}

function plural(n: number): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return "вакансий";
  if (b > 1 && b < 5) return "вакансии";
  if (b === 1) return "вакансия";
  return "вакансий";
}
