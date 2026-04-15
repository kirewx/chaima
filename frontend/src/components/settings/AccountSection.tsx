import { useState, useEffect } from "react";
import {
  Box,
  Stack,
  TextField,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  Typography,
  Divider,
} from "@mui/material";
import LightModeIcon from "@mui/icons-material/LightMode";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import { useNavigate } from "react-router-dom";
import { SectionHeader } from "./SectionHeader";
import { useCurrentUser, useLogout } from "../../api/hooks/useAuth";
import { useUpdateMe } from "../../api/hooks/useUpdateMe";

export function AccountSection() {
  const { data: user } = useCurrentUser();
  const updateMe = useUpdateMe();
  const logout = useLogout();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [pwMsg, setPwMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (user?.email) setEmail(user.email);
  }, [user?.email]);

  if (!user) return <SectionHeader title="Account" />;

  const emailDirty = email.trim().length > 0 && email.trim() !== user.email;

  const saveEmail = async () => {
    await updateMe.mutateAsync({ email: email.trim() });
  };

  const savePassword = async () => {
    if (!newPassword) return;
    try {
      // TODO: fastapi-users PATCH /users/me does not require current_password;
      // the session cookie proves identity. Current-password field is UX-only
      // for v1. If the security posture tightens, enforce re-auth server-side
      // and surface the error here.
      await updateMe.mutateAsync({ password: newPassword });
      setPwMsg({ kind: "ok", text: "Password updated." });
      setCurrentPassword("");
      setNewPassword("");
    } catch (e) {
      setPwMsg({ kind: "err", text: e instanceof Error ? e.message : "Failed to update password." });
    }
  };

  const setMode = async (mode: "light" | "dark") => {
    await updateMe.mutateAsync({ dark_mode: mode === "dark" });
  };

  return (
    <Box>
      <SectionHeader
        title="Account"
        subtitle="Your profile, security, and appearance preferences."
      />

      <Stack spacing={4}>
        <Stack spacing={1.5}>
          <Typography variant="h4">Profile</Typography>
          <TextField
            label="Email"
            size="small"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            sx={{ maxWidth: 360 }}
          />
          <Box>
            <Button
              variant="contained"
              size="small"
              disabled={!emailDirty || updateMe.isPending}
              onClick={saveEmail}
            >
              Save email
            </Button>
          </Box>
        </Stack>

        <Divider />

        <Stack spacing={1.5}>
          <Typography variant="h4">Password</Typography>
          <TextField
            label="Current password"
            type="password"
            size="small"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            sx={{ maxWidth: 360 }}
            autoComplete="current-password"
          />
          <TextField
            label="New password"
            type="password"
            size="small"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            sx={{ maxWidth: 360 }}
            autoComplete="new-password"
          />
          {pwMsg && (
            <Alert severity={pwMsg.kind === "ok" ? "success" : "error"} sx={{ maxWidth: 360 }}>
              {pwMsg.text}
            </Alert>
          )}
          <Box>
            <Button
              variant="contained"
              size="small"
              disabled={!currentPassword || !newPassword || updateMe.isPending}
              onClick={savePassword}
            >
              Update password
            </Button>
          </Box>
        </Stack>

        <Divider />

        <Stack spacing={1.5}>
          <Typography variant="h4">Theme</Typography>
          <Typography variant="body2" color="text.secondary">
            Persisted to your account. Applies immediately across all your browsers.
          </Typography>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={user.dark_mode ? "dark" : "light"}
            onChange={(_, v) => v && setMode(v)}
            aria-label="Theme"
          >
            <ToggleButton value="light" aria-label="Light theme">
              <LightModeIcon fontSize="small" sx={{ mr: 1 }} /> Light
            </ToggleButton>
            <ToggleButton value="dark" aria-label="Dark theme">
              <DarkModeIcon fontSize="small" sx={{ mr: 1 }} /> Dark
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>

        <Divider />

        <Stack spacing={1.5}>
          <Typography variant="h4">Session</Typography>
          <Box>
            <Button
              variant="outlined"
              color="error"
              size="small"
              onClick={() =>
                logout.mutate(undefined, {
                  onSuccess: () => navigate("/login", { replace: true }),
                })
              }
            >
              Sign out
            </Button>
          </Box>
        </Stack>
      </Stack>
    </Box>
  );
}
