import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#2563eb" },
    success: { main: "#4ade80" },
    error: { main: "#f87171" },
    warning: { main: "#fbbf24" },
    background: { default: "#0a0a0a", paper: "#1a1a1a" },
    text: { primary: "#ffffff", secondary: "#888888" },
  },
  shape: { borderRadius: 10 },
  typography: { fontFamily: "'Inter', 'SF Pro Text', system-ui, sans-serif" },
  components: {
    MuiBottomNavigation: { styleOverrides: { root: { backgroundColor: "#111111", borderTop: "1px solid #222222" } } },
    MuiBottomNavigationAction: { styleOverrides: { root: { color: "#666666", "&.Mui-selected": { color: "#2563eb" } } } },
    MuiCard: { styleOverrides: { root: { backgroundColor: "#1a1a1a", backgroundImage: "none" } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
  },
});

export default theme;
