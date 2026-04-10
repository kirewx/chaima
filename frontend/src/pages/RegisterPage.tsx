import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Box, TextField, Button, Typography, Alert, Link, Paper } from "@mui/material";
import { useRegister } from "../api/hooks/useAuth";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const navigate = useNavigate();
  const register = useRegister();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password !== confirmPassword) { setLocalError("Passwords do not match"); return; }
    register.mutate({ email, password }, { onSuccess: () => navigate("/login") });
  };

  const errorMessage = localError ?? (register.isError ? "Registration failed. Email may already be in use." : null);

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: "100%" }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>ChAIMa</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>Create a new account</Typography>
        {errorMessage && <Alert severity="error" sx={{ mb: 2 }}>{errorMessage}</Alert>}
        <Box component="form" onSubmit={handleSubmit}>
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required autoFocus sx={{ mb: 2 }} />
          <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required sx={{ mb: 2 }} slotProps={{ htmlInput: { "aria-label": "Password" } }} />
          <TextField label="Confirm Password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} fullWidth required sx={{ mb: 3 }} slotProps={{ htmlInput: { "aria-label": "Confirm Password" } }} />
          <Button type="submit" variant="contained" fullWidth size="large" disabled={register.isPending}>
            {register.isPending ? "Creating account..." : "Register"}
          </Button>
        </Box>
        <Typography variant="body2" sx={{ mt: 2, textAlign: "center" }}>
          Already have an account? <Link component={RouterLink} to="/login">Sign in</Link>
        </Typography>
      </Paper>
    </Box>
  );
}
