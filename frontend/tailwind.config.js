/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
      },
      colors: {
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        "surface-2": "var(--color-surface-2)",
        border: "var(--color-border)",
        text: "var(--color-text)",
        muted: "var(--color-muted)",
        correct: "var(--color-correct)",
        partial: "var(--color-partial)",
        wrong: "var(--color-wrong)",
        stuck: "var(--color-stuck)",
        ink: {
          950: "#0c1222",
          900: "#111827",
          800: "#1e293b",
          700: "#334155",
          600: "#475569",
          500: "#64748b",
          400: "#94a3b8",
          300: "#cbd5e1",
        },
        mist: { 50: "#f8fafc", 100: "#f1f5f9", 200: "#e2e8f0", 300: "#cbd5e1", 400: "#94a3b8" },
        accent: {
          DEFAULT: "var(--color-accent)",
          dim: "var(--color-accent-dim)",
          light: "#9a8cff",
          50: "#eef2ff",
        },
      },
      keyframes: {
        spotlight: {
          "0%": { opacity: "0", transform: "translate(-72%, -62%) scale(0.5)" },
          "100%": { opacity: "1", transform: "translate(-50%,-40%) scale(1)" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulse_dot: {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
      },
      animation: {
        shimmer: "shimmer 2s infinite",
        spotlight: "spotlight 2s ease .75s 1 forwards",
        "fade-up": "fade-up 0.4s ease-out both",
        pulse_dot: "pulse_dot 1.4s infinite ease-in-out both",
      },
    },
  },
  plugins: [],
};
