/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#121315",
        surface: "#121315",
        "surface-container-lowest": "#0d0e10",
        "surface-container-low": "#1b1c1e",
        "surface-container": "#1f2022",
        "surface-container-high": "#292a2c",
        "surface-container-highest": "#343537",
        "surface-bright": "#38393b",
        "on-surface": "#e3e2e5",
        "on-surface-variant": "#b9cbbb",
        outline: "#849586",
        "outline-variant": "#3b4b3e",
        primary: "#f2fff1",
        "primary-container": "#00ff94",
        "primary-fixed": "#5bffa1",
        "primary-fixed-dim": "#00e383",
        "on-primary-container": "#00713f",
        secondary: "#ffb4ab",
        "secondary-container": "#d30017",
        "on-secondary-container": "#ffe2de",
        "tertiary-fixed-dim": "#4cd6ff"
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem"
      },
      spacing: {
        gutter: "1px",
        "module-padding": "12px",
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px"
      },
      fontFamily: {
        h1: ["Inter", "ui-sans-serif", "system-ui"],
        h2: ["Inter", "ui-sans-serif", "system-ui"],
        "data-mono": ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        "label-caps": ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        "body-md": ["IBM Plex Sans", "Inter", "ui-sans-serif", "system-ui"],
        "body-sm": ["IBM Plex Sans", "Inter", "ui-sans-serif", "system-ui"]
      },
      fontSize: {
        h1: ["24px", { lineHeight: "32px", letterSpacing: "-0.02em", fontWeight: "600" }],
        h2: ["18px", { lineHeight: "24px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "data-mono": ["13px", { lineHeight: "18px", letterSpacing: "0.02em", fontWeight: "500" }],
        "body-md": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "body-sm": ["12px", { lineHeight: "16px", fontWeight: "400" }],
        "label-caps": ["10px", { lineHeight: "12px", letterSpacing: "0.08em", fontWeight: "700" }]
      },
      boxShadow: {
        "terminal-glow": "0 0 24px rgba(0, 255, 148, 0.12)",
        "cyan-glow": "0 0 24px rgba(76, 214, 255, 0.14)"
      }
    }
  },
  plugins: []
};
