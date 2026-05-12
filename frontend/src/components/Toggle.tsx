interface Props {
  on: boolean;
  onChange: (v: boolean) => void;
  ariaLabel?: string;
}

export function Toggle({ on, onChange, ariaLabel }: Props) {
  return (
    <button
      role="switch"
      type="button"
      aria-checked={on}
      aria-label={ariaLabel}
      onClick={(e) => {
        // Тумблер часто живёт внутри clickable Row — не даём клику
        // пробрасываться, иначе Row тоже сработает и состояние «дёрнется».
        e.stopPropagation();
        onChange(!on);
      }}
      className="relative transition-colors"
      style={{
        width: 44,
        height: 26,
        borderRadius: 13,
        background: on ? "var(--accent)" : "#23272F",
      }}
    >
      <span
        className="absolute transition-all"
        style={{
          top: 3,
          left: on ? 21 : 3,
          width: 20,
          height: 20,
          borderRadius: 10,
          background: on ? "var(--accent-on)" : "#fff",
        }}
      />
    </button>
  );
}
