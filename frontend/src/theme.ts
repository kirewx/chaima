import { createTheme } from "@mui/material/styles";

const ink = "#161514";
const paper = "#faf8f3";
const surface = "#ffffff";
const hairline = "#e6e0d4";
const muted = "#7a7268";
const accent = "#b8431c";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: accent, contrastText: "#ffffff" },
    success: { main: "#4f7a3a" },
    error: { main: "#a8321a" },
    warning: { main: "#c4831f" },
    background: { default: paper, paper: surface },
    text: { primary: ink, secondary: muted },
    divider: hairline,
  },
  shape: { borderRadius: 4 },
  typography: {
    fontFamily: "'Geist', system-ui, -apple-system, sans-serif",
    h1: { fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500, letterSpacing: "-0.02em" },
    h2: { fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500, letterSpacing: "-0.02em" },
    h3: { fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500, letterSpacing: "-0.015em" },
    h4: { fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500, letterSpacing: "-0.01em" },
    h5: { fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500 },
    h6: { fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500 },
    body1: { fontSize: 15, lineHeight: 1.55 },
    body2: { fontSize: 13.5, lineHeight: 1.5 },
    button: { textTransform: "none", fontWeight: 500, letterSpacing: 0 },
    caption: { fontSize: 11.5, letterSpacing: "0.02em" },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: paper,
          fontFeatureSettings: "'ss01', 'cv11'",
        },
      },
    },
    MuiBottomNavigation: {
      styleOverrides: {
        root: {
          backgroundColor: surface,
          borderTop: `1px solid ${hairline}`,
          height: 60,
        },
      },
    },
    MuiBottomNavigationAction: {
      styleOverrides: {
        root: {
          color: muted,
          "&.Mui-selected": { color: ink },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: surface,
          backgroundImage: "none",
          boxShadow: "none",
          border: `1px solid ${hairline}`,
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
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          letterSpacing: "0.01em",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 2 },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: surface,
          borderRadius: 2,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 2 },
      },
    },
  },
});

export default theme;
