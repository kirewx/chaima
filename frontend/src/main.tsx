import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, useLocation } from "react-router-dom";
import { GroupProvider } from "./components/GroupContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useAppTheme } from "./hooks/useTheme";
import App from "./App";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

function RoutedApp() {
  // Reset the error boundary on navigation so a broken page recovers when
  // the user clicks away, instead of staying stuck on the fallback.
  const location = useLocation();
  return (
    <ErrorBoundary resetKey={location.pathname}>
      <App />
    </ErrorBoundary>
  );
}

function ThemedApp() {
  const theme = useAppTheme();
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <GroupProvider>
          <RoutedApp />
        </GroupProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemedApp />
    </QueryClientProvider>
  </StrictMode>,
);
