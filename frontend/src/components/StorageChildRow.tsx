import { Box, Typography, IconButton, Tooltip } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { useNavigate } from "react-router-dom";
import type { StorageLocationNode } from "../types";
import { RoleGate } from "./RoleGate";
import { useDrawer } from "./drawer/DrawerContext";

export function StorageChildRow({ node }: { node: StorageLocationNode }) {
  const navigate = useNavigate();
  const { open } = useDrawer();
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/storage/${node.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") navigate(`/storage/${node.id}`);
      }}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        px: 1.5,
        py: 1.25,
        minHeight: 44,
        borderBottom: "1px solid",
        borderColor: "divider",
        cursor: "pointer",
        transition: "background-color 120ms",
        "&:hover": { bgcolor: "action.hover", "& .edit-btn": { opacity: 1 } },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" sx={{ fontWeight: 500, color: "text.primary", lineHeight: 1.3 }} noWrap>
          {node.name}
        </Typography>
        {node.description && (
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
            {node.description}
          </Typography>
        )}
      </Box>
      <RoleGate allow={["admin", "superuser"]}>
        <Tooltip title="Edit">
          <IconButton
            size="small"
            className="edit-btn"
            onClick={(e) => {
              e.stopPropagation();
              open({ kind: "storage-edit", locationId: node.id });
            }}
            sx={{ opacity: 0, "&:focus": { opacity: 1 } }}
          >
            <EditIcon fontSize="inherit" sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </RoleGate>
      <Box
        sx={{
          minWidth: 32,
          textAlign: "right",
          fontVariantNumeric: "tabular-nums",
          fontSize: 12,
          color: "text.secondary",
          fontWeight: 500,
        }}
      >
        {node.container_count}
      </Box>
    </Box>
  );
}
