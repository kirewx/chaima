import { Box, Typography, ButtonBase } from "@mui/material";
import type { ChemicalRead, ContainerRead } from "../types";

interface ChemicalRowProps {
  chemical: ChemicalRead;
  container: ContainerRead | null;
  locationPath?: string;
  selected?: boolean;
  onClick?: () => void;
}

const mono = "'JetBrains Mono', ui-monospace, monospace";

export default function ChemicalCard({ chemical, container, locationPath, selected, onClick }: ChemicalRowProps) {
  const hasContainer = container !== null;

  return (
    <ButtonBase
      component="div"
      onClick={onClick}
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "10px 1fr auto", md: "14px 1fr 1.2fr 130px" },
        gridTemplateRows: { xs: "auto auto", md: "auto" },
        alignItems: "center",
        gap: { xs: "2px 10px", md: "0 16px" },
        width: "100%",
        textAlign: "left",
        px: { xs: 2, md: 2.5 },
        py: 1.25,
        minHeight: 36,
        borderBottom: "1px solid",
        borderColor: "divider",
        bgcolor: selected ? "primary.main" : "transparent",
        backgroundColor: selected ? "rgba(48, 107, 130, 0.09)" : "transparent",
        boxShadow: selected ? "inset 3px 0 0 #306b82" : "none",
        "&:hover": {
          backgroundColor: selected ? "rgba(48, 107, 130, 0.11)" : "background.paper",
        },
      }}
    >
      <Box
        sx={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          bgcolor: hasContainer ? "success.main" : "transparent",
          border: hasContainer ? "none" : "1px solid",
          borderColor: "text.secondary",
          gridRow: { xs: "1 / 3", md: "auto" },
          alignSelf: "center",
          justifySelf: "center",
        }}
      />

      <Typography
        sx={{
          fontSize: 14,
          fontWeight: 500,
          color: hasContainer ? "text.primary" : "text.secondary",
          lineHeight: 1.3,
          gridColumn: { xs: 2, md: 2 },
          gridRow: { xs: 1, md: "auto" },
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {chemical.name}
      </Typography>

      {hasContainer && (
        <Typography
          sx={{
            fontFamily: mono,
            fontSize: 11,
            color: "text.secondary",
            gridColumn: { xs: 2, md: 3 },
            gridRow: { xs: 2, md: "auto" },
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {locationPath ?? "—"}
        </Typography>
      )}

      {hasContainer && (
        <Typography
          sx={{
            fontFamily: mono,
            fontSize: 10,
            color: selected ? "primary.main" : "text.secondary",
            textAlign: { xs: "left", md: "right" },
            gridColumn: { xs: 3, md: 4 },
            gridRow: { xs: "1 / 3", md: "auto" },
            alignSelf: "center",
            justifySelf: { xs: "end", md: "end" },
            letterSpacing: "0.04em",
          }}
        >
          {container.identifier}
        </Typography>
      )}
    </ButtonBase>
  );
}
