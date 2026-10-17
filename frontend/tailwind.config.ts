import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: { DEFAULT: "#EDEDED", canvas: "#F5F5F5" },
        surface: { DEFAULT: "#FFFFFF", muted: "#EFEFEF" },
        accent: { DEFAULT: "#F0510F", hover: "#D9450A", soft: "#FDEBE3" },
        brown: "#3D2416",
        beige: "#E4DDD2",
        ink: { DEFAULT: "#111111", muted: "#7A7A7A" },
        line: "#E6E6E6",
        negative: "#E5481B",
        status: {
          resolved: "#22A06B",
          pending: "#E8A33D",
          open: "#5B6B7F",
          progress: "#F0510F",
          closed: "#9A9A9A",
          reopened: "#7A5AF8",
        },
      },
      borderRadius: {
        card: "24px",
        control: "9999px",
      },
      fontFamily: {
        sans: ["var(--font-manrope)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(17,17,17,0.04), 0 8px 24px rgba(17,17,17,0.04)",
        pop: "0 12px 40px rgba(17,17,17,0.12)",
        rail: "0 0 0 1px rgba(17,17,17,0.04)",
      },
    },
  },
  plugins: [],
};
export default config;
