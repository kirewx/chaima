import { useState, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Divider,
} from "@mui/material";
import { useInviteInfo, useAcceptInviteNewUser, useAcceptInviteExistingUser } from "../api/hooks/useInvites";
import { useCurrentUser, useLogin } from "../api/hooks/useAuth";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const inviteQuery = useInviteInfo(token ?? "");
  const userQuery = useCurrentUser();
  const acceptNew = useAcceptInviteNewUser(token ?? "");
  const acceptExisting = useAcceptInviteExistingUser(token ?? "");
  const login = useLogin();

  const [mode, setMode] = useState<"choice" | "login" | "register">("choice");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const isLoggedIn = !!userQuery.data;
  const invite = inviteQuery.data;

  if (inviteQuery.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (inviteQuery.isError || !invite) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
        <Paper sx={{ p: 4, maxWidth: 400, width: "100%", textAlign: "center" }}>
          <Typography variant="h5" sx={{ mb: 2 }}>Invalid Invite</Typography>
          <Typography color="text.secondary">This invite link is invalid or has been removed.</Typography>
        </Paper>
      </Box>
    );
  }

  if (!invite.is_valid) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
        <Paper sx={{ p: 4, maxWidth: 400, width: "100%", textAlign: "center" }}>
          <Typography variant="h5" sx={{ mb: 2 }}>Invite Expired</Typography>
          <Typography color="text.secondary">This invite has expired or has already been used.</Typography>
        </Paper>
      </Box>
    );
  }

  const handleAcceptLoggedIn = () => {
    acceptExisting.mutate(undefined, {
      onSuccess: () => navigate("/"),
    });
  };

  const handleRegister = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }
    acceptNew.mutate(
      { email, password },
      {
        onSuccess: () => {
          login.mutate(
            { username: email, password },
            { onSuccess: () => navigate("/") },
          );
        },
        onError: () => setLocalError("Registration failed. Email may already be in use."),
      },
    );
  };

  const handleLogin = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    login.mutate(
      { username: email, password },
      {
        onSuccess: () => {
          acceptExisting.mutate(undefined, {
            onSuccess: () => navigate("/"),
          });
        },
        onError: () => setLocalError("Invalid email or password"),
      },
    );
  };

  const errorMessage = localError ?? (acceptNew.isError ? "Failed to create account" : null);

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: "100%" }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>ChAIMa</Typography>
        <Typography variant="h6" sx={{ mb: 1 }}>
          You've been invited to <strong>{invite.group_name}</strong>
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Accept to join this group.
        </Typography>

        {errorMessage && <Alert severity="error" sx={{ mb: 2 }}>{errorMessage}</Alert>}

        {isLoggedIn ? (
          <Box>
            <Typography variant="body2" sx={{ mb: 2 }}>
              Logged in as {userQuery.data?.email}
            </Typography>
            <Button variant="contained" fullWidth onClick={handleAcceptLoggedIn} disabled={acceptExisting.isPending}>
              {acceptExisting.isPending ? "Joining..." : "Accept Invite"}
            </Button>
          </Box>
        ) : mode === "choice" ? (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Button variant="contained" fullWidth onClick={() => setMode("register")}>
              Create Account
            </Button>
            <Button variant="outlined" fullWidth onClick={() => setMode("login")}>
              I already have an account
            </Button>
          </Box>
        ) : mode === "register" ? (
          <Box component="form" onSubmit={handleRegister}>
            <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required autoFocus sx={{ mb: 2 }} />
            <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required sx={{ mb: 2 }} />
            <TextField label="Confirm Password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} fullWidth required sx={{ mb: 3 }} />
            <Button type="submit" variant="contained" fullWidth disabled={acceptNew.isPending}>
              {acceptNew.isPending ? "Creating account..." : "Create Account & Join"}
            </Button>
            <Divider sx={{ my: 2 }} />
            <Button variant="text" fullWidth onClick={() => setMode("choice")}>Back</Button>
          </Box>
        ) : (
          <Box component="form" onSubmit={handleLogin}>
            <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required autoFocus sx={{ mb: 2 }} />
            <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required sx={{ mb: 3 }} />
            <Button type="submit" variant="contained" fullWidth disabled={login.isPending}>
              {login.isPending ? "Signing in..." : "Sign in & Join"}
            </Button>
            <Divider sx={{ my: 2 }} />
            <Button variant="text" fullWidth onClick={() => setMode("choice")}>Back</Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
