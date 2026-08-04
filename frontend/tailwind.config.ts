import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "var(--bg)",
          panel: "var(--panel)",
          elevated: "var(--elevated)",
          border: "var(--border)",
          muted: "var(--muted)",
          text: "var(--text)",
          dim: "var(--dim)",
          accent: "var(--accent)",
          gain: "var(--gain)",
          loss: "var(--loss)",
          warn: "var(--warn)",
          danger: "var(--danger)",
          live: "var(--live)",
          info: "var(--info)",
          focus: "var(--focus)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        terminal: "var(--shadow)",
      },
      minHeight: {
        touch: "44px",
      },
      minWidth: {
        touch: "44px",
      },
    },
  },
  plugins: [],
};

export default config;
