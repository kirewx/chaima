import { Alert, IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Divider, Snackbar } from "@mui/material";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import EditIcon from "@mui/icons-material/Edit";
import ArchiveIcon from "@mui/icons-material/Archive";
import UnarchiveIcon from "@mui/icons-material/Unarchive";
import LockIcon from "@mui/icons-material/Lock";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import { useState, type MouseEvent } from "react";
import type { ChemicalRead } from "../types";
import {
  useArchiveChemical,
  useUnarchiveChemical,
  useUpdateChemical,
} from "../api/hooks/useChemicals";
import { useDrawer } from "./drawer/DrawerContext";
import { RoleGate } from "./RoleGate";
import { useCurrentUser } from "../api/hooks/useAuth";
import { errorMessage } from "../utils/errorMessage";

interface Props {
  chemical: ChemicalRead;
  /** Group the chemical belongs to. Falls back to the user's main group. */
  groupId?: string;
}

export function ChemicalMenu({ chemical, groupId: groupIdProp }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { open } = useDrawer();
  const { data: user } = useCurrentUser();
  const groupId = groupIdProp ?? user?.main_group_id ?? "";
  const archive = useArchiveChemical(groupId, chemical.id);
  const unarchive = useUnarchiveChemical(groupId, chemical.id);
  const update = useUpdateChemical(groupId, chemical.id);
  const close = () => setAnchor(null);

  const onButtonClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setAnchor(e.currentTarget);
  };

  const onEdit = () => {
    close();
    open({ kind: "chemical-edit", chemicalId: chemical.id, groupId });
  };
  const onArchive = async () => {
    try {
      await archive.mutateAsync();
    } catch (e) {
      setError(errorMessage(e, "Could not archive the chemical."));
    }
    close();
  };
  const onUnarchive = async () => {
    try {
      await unarchive.mutateAsync();
    } catch (e) {
      setError(errorMessage(e, "Could not unarchive the chemical."));
    }
    close();
  };
  const onToggleSecret = async () => {
    try {
      await update.mutateAsync({ is_secret: !chemical.is_secret });
    } catch (e) {
      setError(errorMessage(e, "Could not update the chemical."));
    }
    close();
  };

  return (
    <RoleGate allow={["admin", "superuser", "creator"]} creatorId={chemical.created_by}>
      <IconButton
        size="small"
        onClick={onButtonClick}
        aria-label="Chemical actions"
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          bgcolor: "background.paper",
        }}
      >
        <MoreHorizIcon fontSize="small" />
      </IconButton>
      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={close}
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem onClick={onEdit}>
          <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Edit chemical</ListItemText>
        </MenuItem>
        {chemical.is_archived ? (
          <MenuItem onClick={onUnarchive}>
            <ListItemIcon><UnarchiveIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Unarchive</ListItemText>
          </MenuItem>
        ) : (
          <MenuItem onClick={onArchive}>
            <ListItemIcon><ArchiveIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Archive</ListItemText>
          </MenuItem>
        )}
        <Divider />
        <MenuItem onClick={onToggleSecret}>
          <ListItemIcon>
            {chemical.is_secret ? <LockOpenIcon fontSize="small" /> : <LockIcon fontSize="small" />}
          </ListItemIcon>
          <ListItemText>
            {chemical.is_secret ? "Make public" : "Mark as secret"}
          </ListItemText>
        </MenuItem>
      </Menu>
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        onClick={(e) => e.stopPropagation()}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </RoleGate>
  );
}
