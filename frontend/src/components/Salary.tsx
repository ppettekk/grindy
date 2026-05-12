import type { Vacancy } from "../types";
import { formatSalary } from "../lib/format";

interface Props {
  v: Vacancy;
  big?: boolean;
}

export function Salary({ v, big = false }: Props) {
  if (!v.salary_from && !v.salary_to) {
    return <span className="text-text-3 text-[13px]">не указана</span>;
  }
  return (
    <span
      className="font-display font-extrabold leading-none text-text"
      style={{ fontSize: big ? 32 : 18, letterSpacing: "-0.03em" }}
    >
      {formatSalary(v)}
      <span style={{ color: "var(--accent)" }}>₽</span>
      <span
        className="text-text-3 font-semibold"
        style={{ fontSize: big ? 14 : 11, marginLeft: 4 }}
      >
        {v.salary_unit ?? ""}
      </span>
    </span>
  );
}
