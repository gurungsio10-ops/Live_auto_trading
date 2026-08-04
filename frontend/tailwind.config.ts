import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        "background-secondary": "var(--background-secondary)",
        surface: "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        "surface-hover": "var(--surface-hover)",
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        foreground: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        muted: "var(--text-muted)",
        brand: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
          soft: "var(--primary-soft)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
          soft: "var(--primary-soft)",
        },
        positive: {
          DEFAULT: "var(--positive)",
          soft: "var(--positive-soft)",
        },
        negative: {
          DEFAULT: "var(--negative)",
          soft: "var(--negative-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          soft: "var(--warning-soft)",
        },
        info: {
          DEFAULT: "var(--info)",
          soft: "var(--info-soft)",
        },
        terminal: {
          bg: "var(--background)",
          panel: "var(--surface)",
          elevated: "var(--surface-raised)",
          border: "var(--border)",
          muted: "var(--surface-hover)",
          text: "var(--text-primary)",
          dim: "var(--text-secondary)",
          accent: "var(--primary)",
          gain: "var(--positive)",
          loss: "var(--negative)",
          warn: "var(--warning)",
          danger: "var(--negative)",
          live: "var(--negative)",
          info: "var(--info)",
          focus: "var(--focus)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        card: "var(--radius-card)",
        control: "var(--radius-control)",
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        terminal: "var(--shadow-soft)",
      },
      maxWidth: {
        content: "1600px",
      },
      spacing: {
        sidebar: "var(--sidebar-w)",
        header: "var(--header-h)",
        bottomnav: "var(--bottom-nav-h)",
      },
      minHeight: {
        touch: "44px",
        "touch-lg": "48px",
      },
      transitionDuration: {
        ui: "180ms",
      },
    },
  },
  plugins: [],
};

export default config;
