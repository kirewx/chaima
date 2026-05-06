import { Box, Button, Tooltip, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import type { StorageLocationNode, StorageKind } from "../types";
import { StorageChildRow } from "./StorageChildRow";
import { RoleGate } from "./RoleGate";
import { useDrawer } from "./drawer/DrawerContext";

const KIND_LABEL: Record<StorageKind, string> = {
  building: "building",
  room: "room",
  cabinet: "cabinet",
  shelf: "shelf",
};

export interface StorageChildListProps {
  children: StorageLocationNode[];
  parentId: string | null;
  nextChildKind: StorageKind | null;
  /** Passed through when the add button is clicked — the drawer pre-fills `parent_id`. */
  parentHintForNewChild?: string | null;
  /** If set, the add button is disabled and this string is shown as a tooltip. */
  addDisabledReason?: string | null;
}

export function StorageChildList({
  children,
  parentId,
  nextChildKind,
  parentHintForNewChild,
  addDisabledReason,
}: StorageChildListProps) {
  const { open } = useDrawer();
  const hasChildren = children.length > 0;

  return (
    <Box>
      {hasChildren ? (
        <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1, overflow: "hidden" }}>
          {children.map((c) => (
            <StorageChildRow key={c.id} node={c} />
          ))}
        </Box>
      ) : (
        <Typography color="text.secondary" sx={{ py: 3, textAlign: "center", fontSize: 13 }}>
          {nextChildKind ? `No ${KIND_LABEL[nextChildKind]}s yet.` : "Nothing here."}
        </Typography>
      )}

      {nextChildKind && (
        <RoleGate allow={nextChildKind === "building" ? ["superuser"] : ["admin", "superuser"]}>
          <Box sx={{ mt: 1.5 }}>
            <Tooltip title={addDisabledReason ?? ""} disableHoverListener={!addDisabledReason}>
              <span>
                <Button
                  size="small"
                  startIcon={<AddIcon />}
                  disabled={!!addDisabledReason}
                  onClick={() =>
                    open({
                      kind: "storage-new",
                      childKind: nextChildKind,
                      parentId: parentHintForNewChild ?? parentId,
                    })
                  }
                  sx={{ color: "text.secondary" }}
                >
                  Add {KIND_LABEL[nextChildKind]}
                </Button>
              </span>
            </Tooltip>
          </Box>
        </RoleGate>
      )}
    </Box>
  );
}
