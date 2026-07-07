import { Component, type ErrorInfo, type ReactNode } from "react";
import { Alert, Box, Button, Typography } from "@mui/material";

interface Props {
  children: ReactNode;
  /**
   * When this value changes, a currently-shown error is cleared so the
   * children re-render. Pass the route path so navigating away from a broken
   * page recovers instead of leaving the fallback stuck until a full reload.
   */
  resetKey?: unknown;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time errors anywhere below it and shows a friendly
 * fallback instead of a blank white page.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info);
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <Box sx={{ p: 4, maxWidth: 480, mx: "auto" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
              Something went wrong.
            </Typography>
            <Typography variant="body2">{this.state.error.message}</Typography>
          </Alert>
          <Button
            variant="outlined"
            onClick={() => {
              this.setState({ error: null });
              window.location.assign("/");
            }}
          >
            Back to start
          </Button>
        </Box>
      );
    }
    return this.props.children;
  }
}
