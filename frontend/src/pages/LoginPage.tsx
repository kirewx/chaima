import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Box, TextField, Button, Typography, Alert, Link, Paper } from "@mui/material";
import { useLogin } from "../api/hooks/useAuth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();
  const login = useLogin();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ username: email, password }, { onSuccess: () => navigate("/") });
  };

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: "100%" }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>ChAIMa</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>Sign in to your account</Typography>
        {login.isError && <Alert severity="error" sx={{ mb: 2 }}>Invalid email or password</Alert>}
        <Box component="form" onSubmit={handleSubmit}>
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required autoFocus sx={{ mb: 2 }} />
          <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required sx={{ mb: 3 }} />
          <Button type="submit" variant="contained" fullWidth size="large" disabled={login.isPending}>
            {login.isPending ? "Signing in..." : "Sign in"}
          </Button>
        </Box>
        <Typography variant="body2" sx={{ mt: 2, textAlign: "center" }}>
          No account? <Link component={RouterLink} to="/register">Register</Link>
        </Typography>
      </Paper>
    </Box>
  );
}
