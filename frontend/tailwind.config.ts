import type { Config } from "tailwindcss";

/**
 * Grindy design tokens — взяты 1:1 из handoff/src/tokens.jsx.
 * Цвета — холодные нейтрали, один яркий лаймовый акцент.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg0: "#0A0B0D",
        bg1: "#111317",
        bg2: "#181B21",
        bg3: "#23272F",
        line: "#2A2F38",
        text: {
          DEFAULT: "#F4F5F7",
          2: "#A8ADB7",
          3: "#6E7480",
        },
        warn: "#FFB547",
        danger: "#FF5C57",
        ok: "#3DDC97",
        accent: "var(--accent)",
        "accent-on": "var(--accent-on)",
      },
      fontFamily: {
        display: [
          "Onest",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "monospace",
        ],
      },
      borderRadius: {
        chip: "8px",
        input: "12px",
        sheet: "14px",
        card: "16px",
        cardLg: "18px",
        big: "24px",
      },
      letterSpacing: {
        display: "-0.04em",
        h1: "-0.03em",
        h2: "-0.02em",
        mono: "0.08em",
      },
      boxShadow: {
        phone:
          "0 0 0 9px #1c1d1f, 0 0 0 10px #2a2b2e, 0 30px 60px -20px rgba(0,0,0,0.6)",
      },
    },
  },
  plugins: [],
};

export default config;
