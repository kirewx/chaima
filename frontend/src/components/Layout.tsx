import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  AppBar, Toolbar, Box, Button, IconButton, Avatar, Menu, MenuItem,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import LightModeIcon from "@mui/icons-material/LightMode";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import { useCurrentUser, useLogout } from "../api/hooks/useAuth";
import { useUpdateMe } from "../api/hooks/useUpdateMe";
import { DrawerProvider } from "./drawer/DrawerContext";
import { EditDrawer } from "./drawer/EditDrawer";

const navItems = [
  { to: "/", label: "Chemicals" },
  { to: "/storage", label: "Storage" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const updateMe = useUpdateMe();
  const navigate = useNavigate();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

  const handleSignOut = async () => {
    setMenuAnchor(null);
    await logout.mutateAsync();
    navigate("/login");
  };

  const isDark = !!user?.dark_mode;
  const toggleDarkMode = () => {
    if (!user) return;
    updateMe.mutate({ dark_mode: !user.dark_mode });
  };

  return (
    <DrawerProvider>
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppBar
        position="sticky"
        elevation={0}
        color="default"
        sx={{ borderBottom: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}
      >
        <Toolbar sx={{ minHeight: 52, gap: 2 }}>
          <Box sx={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.01em" }}>
            ChAIMa
          </Box>
          <Box sx={{ display: { xs: "none", sm: "flex" }, gap: 0.5, ml: 2 }}>
            {navItems.map((n) => (
              <Button
                key={n.to}
                component={NavLink}
                to={n.to}
                end={n.to === "/"}
                sx={{
                  color: "text.secondary",
                  px: 1.5,
                  "&.active": { color: "text.primary", fontWeight: 600 },
                }}
              >
                {n.label}
              </Button>
            ))}
          </Box>
          <Box sx={{ flex: 1 }} />
          {user && (
            <IconButton
              onClick={toggleDarkMode}
              disabled={updateMe.isPending}
              aria-label="Toggle dark mode"
              title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            >
              {isDark ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
            </IconButton>
          )}
          <IconButton
            sx={{ display: { xs: "inline-flex", sm: "none" } }}
            onClick={(e) => setMenuAnchor(e.currentTarget)}
            aria-label="Open menu"
          >
            <MenuIcon />
          </IconButton>
          <IconButton
            sx={{ display: { xs: "none", sm: "inline-flex" } }}
            onClick={(e) => setMenuAnchor(e.currentTarget)}
            aria-label="User menu"
          >
            <Avatar sx={{ width: 28, height: 28, fontSize: 12 }}>
              {user?.email?.[0]?.toUpperCase() ?? "?"}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            {/* Mobile-only nav items */}
            <Box sx={{ display: { xs: "block", sm: "none" } }}>
              {navItems.map((n) => (
                <MenuItem
                  key={n.to}
                  onClick={() => { setMenuAnchor(null); navigate(n.to); }}
                >
                  {n.label}
                </MenuItem>
              ))}
              <Box sx={{ borderTop: "1px solid", borderColor: "divider", my: 0.5 }} />
            </Box>
            <MenuItem onClick={() => { setMenuAnchor(null); navigate("/settings"); }}>
              Settings
            </MenuItem>
            <MenuItem onClick={handleSignOut}>Sign out</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
      <Box
        component="main"
        sx={{
          flex: 1,
          maxWidth: 1080,
          width: "100%",
          mx: "auto",
          p: { xs: 2, sm: 3 },
        }}
      >
        <Outlet />
      </Box>
      <EditDrawer />
    </Box>
    </DrawerProvider>
  );
}
