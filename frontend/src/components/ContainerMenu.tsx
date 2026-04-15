import { IconButton, Menu, MenuItem, ListItemIcon, ListItemText } from "@mui/material";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import EditIcon from "@mui/icons-material/Edit";
import ArchiveIcon from "@mui/icons-material/Archive";
import UnarchiveIcon from "@mui/icons-material/Unarchive";
import { useState, type MouseEvent } from "react";
import type { ContainerRead } from "../types";
import { useArchiveContainer, useUnarchiveContainer } from "../api/hooks/useContainers";
import { useDrawer } from "./drawer/DrawerContext";
import { RoleGate } from "./RoleGate";
import { useCurrentUser } from "../api/hooks/useAuth";

interface Props {
  container: ContainerRead;
}

export function ContainerMenu({ container }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const { open } = useDrawer();
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";
  const archive = useArchiveContainer(groupId);
  const unarchive = useUnarchiveContainer(groupId);
  const close = () => setAnchor(null);

  const onButtonClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setAnchor(e.currentTarget);
  };

  const onEdit = () => {
    close();
    open({ kind: "container-edit", containerId: container.id });
  };
  const onArchive = async () => {
    await archive.mutateAsync(container.id);
    close();
  };
  const onUnarchive = async () => {
    await unarchive.mutateAsync(container.id);
    close();
  };

  return (
    <RoleGate allow={["admin", "superuser", "creator"]} creatorId={container.created_by}>
      <IconButton
        size="small"
        onClick={onButtonClick}
        aria-label="Container actions"
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          bgcolor: "background.paper",
          p: 0.25,
        }}
      >
        <MoreHorizIcon sx={{ fontSize: 14 }} />
      </IconButton>
      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={close}
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem onClick={onEdit}>
          <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Edit container</ListItemText>
        </MenuItem>
        {container.is_archived ? (
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
      </Menu>
    </RoleGate>
  );
}
