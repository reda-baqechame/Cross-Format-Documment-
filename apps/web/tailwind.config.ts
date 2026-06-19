import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      colors: {
        ink: "#0b1220",
        canvas: "#f7f9fc",
        chrome: "#eef3f8",
        line: "#e2e8f0",
        // Confident primary (refined indigo-blue) — the single brand accent.
        brand: {
          50: "#eff5ff",
          100: "#dbe7fe",
          200: "#bfd3fe",
          300: "#93b4fd",
          400: "#608ef9",
          500: "#3b6af3",
          600: "#2451e6",
          700: "#1d40c8",
          800: "#1e3aa1",
          900: "#1e367f",
        },
        // Secondary — trust/verification teal.
        trust: {
          50: "#ecfdf6",
          100: "#cffbeb",
          200: "#a0f3d8",
          300: "#5fe6c0",
          400: "#2fd0a8",
          500: "#13b48d",
          600: "#0d9374",
          700: "#0f765f",
          800: "#115d4d",
          900: "#114c40",
        },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)",
        card: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px -12px rgba(15,23,42,0.18)",
        pop: "0 12px 32px -8px rgba(15,23,42,0.22)",
        focus: "0 0 0 3px rgba(59,106,243,0.18)",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.15s ease-out",
        "slide-up": "slide-up 0.2s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
