import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        canvas: "#f6f8fb",
        chrome: "#eef3f8",
        line: "#d9e2ec",
        trust: {
          50: "#ecfdf8",
          100: "#ccfbef",
          600: "#0d9488",
          700: "#0f766e",
        },
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
        },
      },
    },
  },
  plugins: [],
};

export default config;
