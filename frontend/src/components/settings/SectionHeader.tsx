import { Box, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function SectionHeader({ title, subtitle, actions }: Props) {
  return (
    <Stack
      direction="row"
      sx={{
        alignItems: "flex-start",
        justifyContent: "space-between",
        pb: 2,
        mb: 2.5,
        borderBottom: "1px solid",
        borderColor: "divider",
      }}
    >
      <Box>
        <Typography variant="h2">{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {actions && <Box>{actions}</Box>}
    </Stack>
  );
}
