import { useState, useEffect } from "react";
import { Stack, TextField, Button, Box, Typography, Alert } from "@mui/material";
import {
  useCreateStorageLocation,
  useUpdateStorageLocation,
  useArchiveStorageLocation,
  useStorageLocation,
} from "../../api/hooks/useStorageLocations";
import { useGroup } from "../GroupContext";
import { useDrawer } from "./DrawerContext";
import type { StorageKind } from "../../types";

const KIND_LABEL: Record<StorageKind, string> = {
  building: "Building",
  room: "Room",
  cabinet: "Cabinet",
  shelf: "Shelf",
};

type Props =
  | { mode: "create"; childKind: StorageKind; parentId: string | null }
  | { mode: "edit"; locationId: string };

export function StorageForm(props: Props) {
  const { groupId } = useGroup();
  const { close } = useDrawer();

  const editQuery = useStorageLocation(
    groupId,
    props.mode === "edit" ? props.locationId : "",
  );
  const existing = props.mode === "edit" ? editQuery.data : undefined;

  const createMut = useCreateStorageLocation(groupId);
  const updateMut = useUpdateStorageLocation(
    groupId,
    props.mode === "edit" ? props.locationId : "",
  );
  const archiveMut = useArchiveStorageLocation(groupId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing) {
      setName(existing.name);
      setDescription(existing.description ?? "");
    }
  }, [existing?.id]);

  const kind: StorageKind =
    props.mode === "create" ? props.childKind : existing?.kind ?? "shelf";
  const title =
    props.mode === "create" ? `New ${KIND_LABEL[kind].toLowerCase()}` : `Edit ${KIND_LABEL[kind].toLowerCase()}`;

  const submitting = createMut.isPending || updateMut.isPending || archiveMut.isPending;

  const onSubmit = async () => {
    setError(null);
    try {
      if (props.mode === "create") {
        await createMut.mutateAsync({
          name: name.trim(),
          kind,
          description: description.trim() || null,
          parent_id: props.parentId ?? null,
        });
      } else {
        await updateMut.mutateAsync({
          name: name.trim(),
          description: description.trim() || null,
        });
      }
      close();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Could not save.");
    }
  };

  const onArchive = async () => {
    if (props.mode !== "edit") return;
    if (!window.confirm(`Archive this ${KIND_LABEL[kind].toLowerCase()}? Containers inside it keep their data but the location will no longer appear in the tree.`)) return;
    try {
      await archiveMut.mutateAsync(props.locationId);
      close();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Could not archive.");
    }
  };

  return (
    <Box sx={{ p: 2.5 }}>
      <Typography variant="h3" sx={{ mb: 2 }}>
        {title}
      </Typography>
      <Stack spacing={2}>
        <TextField
          label="Name"
          size="small"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <TextField
          label="Description"
          size="small"
          multiline
          minRows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          helperText="Optional — e.g. a shelf note, cabinet contents summary."
        />
        {error && <Alert severity="error">{error}</Alert>}
      </Stack>

      <Stack direction="row" sx={{ mt: 3, justifyContent: "space-between" }}>
        {props.mode === "edit" ? (
          <Button color="error" size="small" onClick={onArchive} disabled={submitting}>
            Archive
          </Button>
        ) : (
          <span />
        )}
        <Stack direction="row" spacing={1}>
          <Button size="small" onClick={close} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            size="small"
            onClick={onSubmit}
            disabled={!name.trim() || submitting}
          >
            {props.mode === "create" ? "Create" : "Save"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}
