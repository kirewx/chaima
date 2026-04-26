import { Box, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

export type SettingsSectionKey =
  | "account"
  | "group"
  | "members"
  | "hazard-tags"
  | "suppliers"
  | "projects"
  | "import"
  | "chemicals-admin"
  | "groups"
  | "buildings"
  | "system";

export interface NavItem {
  key: SettingsSectionKey;
  label: string;
  group: "PERSONAL" | "GROUP ADMIN" | "SUPERUSER" | "SYSTEM";
  visible: boolean;
}

interface Props {
  items: NavItem[];
  active: SettingsSectionKey;
  onSelect: (key: SettingsSectionKey) => void;
  footer?: ReactNode;
}

export function SettingsNav({ items, active, onSelect, footer }: Props) {
  const groups: Array<NavItem["group"]> = ["PERSONAL", "GROUP ADMIN", "SUPERUSER", "SYSTEM"];
  return (
    <Box
      component="nav"
      aria-label="Settings sections"
      sx={{
        width: { xs: "100%", md: 220 },
        flexShrink: 0,
        borderRight: { md: "1px solid" },
        borderBottom: { xs: "1px solid", md: "none" },
        borderColor: "divider",
        pr: { md: 2 },
        pb: { xs: 2, md: 0 },
        mb: { xs: 2, md: 0 },
      }}
    >
      <Stack spacing={2.5}>
        {groups.map((g) => {
          const rows = items.filter((i) => i.group === g && i.visible);
          if (rows.length === 0) return null;
          return (
            <Box key={g}>
              <Typography
                variant="h5"
                sx={{ color: "text.secondary", mb: 0.5, pl: 1 }}
              >
                {g}
              </Typography>
              <Stack>
                {rows.map((r) => {
                  const selected = r.key === active;
                  return (
                    <Box
                      key={r.key}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelect(r.key)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(r.key);
                        }
                      }}
                      sx={{
                        px: 1,
                        py: 0.75,
                        borderRadius: 1,
                        cursor: "pointer",
                        fontSize: 13,
                        fontWeight: selected ? 600 : 400,
                        color: selected ? "text.primary" : "text.secondary",
                        bgcolor: selected ? "action.selected" : "transparent",
                        "&:hover": { bgcolor: "action.hover" },
                      }}
                    >
                      {r.label}
                    </Box>
                  );
                })}
              </Stack>
            </Box>
          );
        })}
      </Stack>
      {footer && <Box sx={{ mt: 3 }}>{footer}</Box>}
    </Box>
  );
}
