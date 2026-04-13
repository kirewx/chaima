import { createTheme } from "@mui/material/styles";

const paper = "#f6f4ef";
const surface = "#fbfaf5";
const ink = "#1a1715";
const muted = "#7a6f60";
const rule = "#dcd5c5";
const ruleSoft = "#e6e0d0";
const accent = "#306b82";
const accentSoft = "#e4edf2";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: accent, contrastText: "#ffffff" },
    success: { main: "#5b8038" },
    error: { main: "#a8321a" },
    warning: { main: "#c4831f" },
    background: { default: paper, paper: surface },
    text: { primary: ink, secondary: muted },
    divider: rule,
  },
  shape: { borderRadius: 3 },
  typography: {
    fontFamily: "'Geist', -apple-system, system-ui, sans-serif",
    fontSize: 14,
    h1: { fontWeight: 600, fontSize: 28, letterSpacing: "-0.02em", lineHeight: 1.1 },
    h2: { fontWeight: 600, fontSize: 22, letterSpacing: "-0.02em", lineHeight: 1.15 },
    h3: { fontWeight: 600, fontSize: 18, letterSpacing: "-0.01em" },
    h4: { fontWeight: 600, fontSize: 16, letterSpacing: "-0.005em" },
    h5: { fontWeight: 600, fontSize: 14 },
    h6: { fontWeight: 600, fontSize: 13 },
    body1: { fontSize: 14, lineHeight: 1.5 },
    body2: { fontSize: 13, lineHeight: 1.5 },
    button: { textTransform: "none", fontWeight: 500, letterSpacing: 0 },
    caption: { fontSize: 11, letterSpacing: "0.02em" },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: paper },
      },
    },
    MuiBottomNavigation: {
      styleOverrides: {
        root: {
          backgroundColor: surface,
          borderTop: `1px solid ${rule}`,
          height: 56,
        },
      },
    },
    MuiBottomNavigationAction: {
      styleOverrides: {
        root: {
          color: muted,
          "&.Mui-selected": { color: accent },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: surface,
          backgroundImage: "none",
          boxShadow: "none",
          border: `1px solid ${rule}`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          borderRadius: 2,
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontSize: 11,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 3 },
        containedPrimary: {
          backgroundColor: ink,
          "&:hover": { backgroundColor: accent },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: surface,
          borderRadius: 3,
          "& fieldset": { borderColor: rule },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 3 },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: { borderColor: ruleSoft },
      },
    },
  },
});

export default theme;
