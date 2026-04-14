import { IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Divider } from "@mui/material";
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

interface Props {
  chemical: ChemicalRead;
}

export function ChemicalMenu({ chemical }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const { open } = useDrawer();
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";
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
    open({ kind: "chemical-edit", chemicalId: chemical.id });
  };
  const onArchive = async () => {
    await archive.mutateAsync();
    close();
  };
  const onUnarchive = async () => {
    await unarchive.mutateAsync();
    close();
  };
  const onToggleSecret = async () => {
    await update.mutateAsync({ is_secret: !chemical.is_secret });
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
    </RoleGate>
  );
}
