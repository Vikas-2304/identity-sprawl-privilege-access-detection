/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0B0E11",
          panel: "#141821",
          raised: "#1B202B",
          line: "#262C38",
        },
        ink: {
          DEFAULT: "#E6E9EF",
          dim: "#8B93A3",
          faint: "#5A6275",
        },
        risk: {
          critical: "#FF3B3B",
          high: "#FF9F1C",
          medium: "#E8C547",
          low: "#2DD4A8",
        },
        signal: "#3DDBFF",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};
