import { useState, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Paper, Typography, TextField, Button, Alert } from "@mui/material";
import { useResetPassword } from "../api/hooks/usePasswordReset";
import { errorMessage } from "../utils/errorMessage";
import { Wordmark } from "../components/Wordmark";

export default function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const reset = useResetPassword();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setLocalError("Password must be at least 8 characters");
      return;
    }
    reset.mutate(
      { token: token ?? "", password },
      { onSuccess: () => setDone(true) },
    );
  };

  if (done) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
        <Paper sx={{ p: 4, maxWidth: 400, width: "100%", textAlign: "center" }}>
          <Typography variant="h5" sx={{ mb: 2 }}>Password updated</Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            You can now sign in with your new password.
          </Typography>
          <Button variant="contained" fullWidth onClick={() => navigate("/login")}>
            Go to sign in
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: "100%" }}>
        <Typography variant="h4" sx={{ mb: 1 }}><Wordmark /></Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Choose a new password
        </Typography>
        {localError && <Alert severity="error" sx={{ mb: 2 }}>{localError}</Alert>}
        {reset.isError && (
          <Alert severity="error" sx={{ mb: 2 }}>{errorMessage(reset.error)}</Alert>
        )}
        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            label="New password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
            required
            autoFocus
            sx={{ mb: 2 }}
          />
          <TextField
            label="Repeat new password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            fullWidth
            required
            sx={{ mb: 3 }}
          />
          <Button type="submit" variant="contained" fullWidth size="large" disabled={reset.isPending}>
            {reset.isPending ? "Saving…" : "Set new password"}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
