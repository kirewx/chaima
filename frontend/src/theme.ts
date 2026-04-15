import { createTheme, type Theme } from "@mui/material/styles";

const light = {
  bg: "#ffffff",
  surface: "#fafbfc",
  ink: "#0f172a",
  muted: "#64748b",
  subtle: "#94a3b8",
  border: "#e2e8f0",
  divider: "#f1f5f9",
  accent: "#4338ca",
  accentSoft: "#eef2ff",
  warn: "#fffbeb",
  warnBorder: "#f59e0b",
  danger: "#b91c1c",
  success: "#059669",
} as const;

const dark = {
  bg: "#0a0a0a",
  surface: "#141414",
  ink: "#e5e5e5",
  muted: "#a3a3a3",
  subtle: "#737373",
  border: "#262626",
  divider: "#1c1c1c",
  accent: "#818cf8",
  accentSoft: "#1e1b4b",
  warn: "#2a2106",
  warnBorder: "#f59e0b",
  danger: "#f87171",
  success: "#4ade80",
} as const;

export const createAppTheme = (mode: "light" | "dark"): Theme => {
  const c = mode === "dark" ? dark : light;
  return createTheme({
    palette: {
      mode,
      primary: { main: c.accent, contrastText: "#ffffff" },
      success: { main: c.success },
      error: { main: c.danger },
      warning: { main: c.warnBorder },
      background: { default: c.bg, paper: c.surface },
      text: { primary: c.ink, secondary: c.muted },
      divider: c.divider,
    },
    shape: { borderRadius: 4 },
    typography: {
      fontFamily: "'Inter', -apple-system, system-ui, sans-serif",
      fontSize: 14,
      h1: { fontWeight: 600, fontSize: 26, letterSpacing: "-0.02em", lineHeight: 1.1 },
      h2: { fontWeight: 600, fontSize: 20, letterSpacing: "-0.015em", lineHeight: 1.15 },
      h3: { fontWeight: 600, fontSize: 16, letterSpacing: "-0.01em" },
      h4: { fontWeight: 600, fontSize: 14 },
      h5: { fontWeight: 600, fontSize: 12, letterSpacing: "0.05em", textTransform: "uppercase" },
      body1: { fontSize: 14, lineHeight: 1.5 },
      body2: { fontSize: 12, lineHeight: 1.5 },
      button: { textTransform: "none", fontWeight: 500, letterSpacing: 0 },
      caption: { fontSize: 11, letterSpacing: "0.02em" },
    },
    components: {
      MuiCssBaseline: { styleOverrides: { body: { backgroundColor: c.bg } } },
      MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: c.surface,
            boxShadow: "none",
            border: `1px solid ${c.border}`,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            "&.MuiButton-contained.MuiButton-colorPrimary": {
              backgroundColor: c.ink,
              color: mode === "dark" ? c.bg : "#ffffff",
              "&:hover": { backgroundColor: c.accent },
            },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: c.surface,
            borderRadius: 4,
            "& fieldset": { borderColor: c.border },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 3, fontSize: 11, fontWeight: 500 },
        },
      },
      MuiDivider: { styleOverrides: { root: { borderColor: c.divider } } },
    },
  });
};

// Default export kept for backwards compatibility until main.tsx migrates.
export default createAppTheme("light");
