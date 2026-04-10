import { useState, useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Box, BottomNavigation, BottomNavigationAction, Drawer,
  List, ListItemButton, ListItemIcon, ListItemText,
  useMediaQuery, useTheme,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import AddIcon from "@mui/icons-material/Add";
import InventoryIcon from "@mui/icons-material/Inventory2";
import SettingsIcon from "@mui/icons-material/Settings";

const NAV_ITEMS = [
  { label: "Search", icon: <SearchIcon />, path: "/" },
  { label: "Add", icon: <AddIcon />, path: "/add" },
  { label: "Storage", icon: <InventoryIcon />, path: "/storage" },
  { label: "Settings", icon: <SettingsIcon />, path: "/settings" },
];

const SIDEBAR_WIDTH = 72;

function pathToIndex(pathname: string): number {
  if (pathname.startsWith("/storage")) return 2;
  if (pathname.startsWith("/settings")) return 3;
  if (pathname.startsWith("/add") || pathname.startsWith("/chemicals")) return 1;
  return 0;
}

export default function Layout() {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const location = useLocation();
  const navigate = useNavigate();
  const [navIndex, setNavIndex] = useState(() => pathToIndex(location.pathname));

  useEffect(() => {
    setNavIndex(pathToIndex(location.pathname));
  }, [location.pathname]);

  const handleNav = (index: number) => {
    setNavIndex(index);
    navigate(NAV_ITEMS[index].path);
  };

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      {isDesktop && (
        <Drawer
          variant="permanent"
          sx={{
            width: SIDEBAR_WIDTH,
            flexShrink: 0,
            "& .MuiDrawer-paper": {
              width: SIDEBAR_WIDTH,
              bgcolor: "#111111",
              borderRight: "1px solid #222222",
              overflowX: "hidden",
            },
          }}
        >
          <Box sx={{ py: 2, textAlign: "center" }}>
            <Box sx={{ fontWeight: 700, color: "primary.main", fontSize: 14, letterSpacing: 1 }}>Ch</Box>
          </Box>
          <List>
            {NAV_ITEMS.map((item, i) => (
              <ListItemButton
                key={item.label}
                selected={navIndex === i}
                onClick={() => handleNav(i)}
                sx={{
                  flexDirection: "column", py: 1.5, px: 0, minHeight: 64,
                  "&.Mui-selected": { color: "primary.main" },
                  color: "text.secondary",
                }}
              >
                <ListItemIcon sx={{ minWidth: 0, justifyContent: "center", color: "inherit" }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.label} slotProps={{ primary: { style: { fontSize: 10, textAlign: "center" } } }} />
              </ListItemButton>
            ))}
          </List>
        </Drawer>
      )}

      <Box component="main" sx={{ flexGrow: 1, pb: isDesktop ? 0 : "56px", minHeight: "100vh" }}>
        <Outlet />
      </Box>

      {!isDesktop && (
        <BottomNavigation
          value={navIndex}
          onChange={(_, newValue) => handleNav(newValue)}
          sx={{ position: "fixed", bottom: 0, left: 0, right: 0, zIndex: theme.zIndex.appBar }}
        >
          {NAV_ITEMS.map((item) => (
            <BottomNavigationAction key={item.label} label={item.label} icon={item.icon} />
          ))}
        </BottomNavigation>
      )}
    </Box>
  );
}
