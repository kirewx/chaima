import { useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import client from "../../api/client";
import {
  useSuppliers,
  useCreateSupplier,
  useUpdateSupplier,
  useDeleteSupplier,
  useSupplierContainers,
} from "../../api/hooks/useSuppliers";
import { SectionHeader } from "./SectionHeader";
import type { SupplierRead } from "../../types";

interface Props {
  groupId: string;
}

type EditState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; supplier: SupplierRead };

export function SuppliersSection({ groupId }: Props) {
  const { data: page, isLoading } = useSuppliers(groupId);
  const suppliers = page?.items ?? [];
  const [editState, setEditState] = useState<EditState>({ mode: "closed" });
  const [deleteState, setDeleteState] = useState<SupplierRead | null>(null);

  return (
    <Box>
      <SectionHeader
        title="Suppliers"
        subtitle="Manage vendors. Deletion is blocked while containers still reference a supplier — reassign them inline."
        actions={
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setEditState({ mode: "create" })}
          >
            New supplier
          </Button>
        }
      />

      {isLoading && (
        <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
          <CircularProgress size={20} />
        </Box>
      )}

      {!isLoading && suppliers.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No suppliers yet. Suppliers are added automatically when you pick them
          on a container, or click <b>New supplier</b>.
        </Typography>
      )}

      {suppliers.length > 0 && (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {suppliers.map((s, i) => (
            <Stack
              key={s.id}
              direction="row"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                alignItems: "center",
                borderBottom: i < suppliers.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }} noWrap>
                  {s.name}
                </Typography>
              </Box>
              <Chip
                size="small"
                label={`${s.container_count ?? 0} container${s.container_count === 1 ? "" : "s"}`}
                variant={(s.container_count ?? 0) === 0 ? "outlined" : "filled"}
                color={(s.container_count ?? 0) === 0 ? "default" : "primary"}
              />
              <IconButton
                size="small"
                onClick={() => setEditState({ mode: "edit", supplier: s })}
                aria-label={`Edit ${s.name}`}
              >
                <EditIcon fontSize="small" />
              </IconButton>
              <IconButton
                size="small"
                onClick={() => setDeleteState(s)}
                aria-label={`Delete ${s.name}`}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
        </Stack>
      )}

      <SupplierEditDialog
        state={editState}
        onClose={() => setEditState({ mode: "closed" })}
        groupId={groupId}
      />
      <SupplierDeleteDialog
        supplier={deleteState}
        onClose={() => setDeleteState(null)}
        groupId={groupId}
        suppliers={suppliers}
      />
    </Box>
  );
}

function SupplierEditDialog({
  state,
  onClose,
  groupId,
}: {
  state: EditState;
  onClose: () => void;
  groupId: string;
}) {
  const create = useCreateSupplier(groupId);
  const update = useUpdateSupplier(
    groupId,
    state.mode === "edit" ? state.supplier.id : "",
  );

  const [name, setName] = useState("");
  const [lastKey, setLastKey] = useState<string>("");
  const open = state.mode !== "closed";
  const key = state.mode === "edit" ? `edit-${state.supplier.id}` : state.mode;

  if (open && lastKey !== key) {
    setName(state.mode === "edit" ? state.supplier.name : "");
    setLastKey(key);
  }
  if (!open && lastKey !== "") {
    setLastKey("");
  }

  const saving = create.isPending || update.isPending;
  const err = create.error || update.error;
  const errMessage =
    err instanceof AxiosError
      ? (err.response?.data?.detail ?? err.message)
      : err instanceof Error
        ? err.message
        : null;

  const submit = async () => {
    if (state.mode === "create") {
      await create.mutateAsync({ name });
    } else if (state.mode === "edit") {
      await update.mutateAsync({ name });
    }
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        {state.mode === "edit" ? "Rename supplier" : "New supplier"}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {errMessage && <Alert severity="error">{String(errMessage)}</Alert>}
          <TextField
            label="Name"
            size="small"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!name.trim() || saving}
        >
          {state.mode === "edit" ? "Save" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function SupplierDeleteDialog({
  supplier,
  onClose,
  groupId,
  suppliers,
}: {
  supplier: SupplierRead | null;
  onClose: () => void;
  groupId: string;
  suppliers: SupplierRead[];
}) {
  const remove = useDeleteSupplier(groupId);
  const { data: containers, isLoading } = useSupplierContainers(
    groupId,
    supplier?.id ?? null,
  );

  const otherSuppliers = suppliers.filter((s) => s.id !== supplier?.id);

  const confirmDelete = async () => {
    if (!supplier) return;
    await remove.mutateAsync(supplier.id);
    onClose();
  };

  const removeErr =
    remove.error instanceof AxiosError
      ? (remove.error.response?.data?.detail?.message ??
        remove.error.response?.data?.detail ??
        remove.error.message)
      : null;

  const containerList = Array.isArray(containers) ? containers : [];
  const containerCount = Array.isArray(containers)
    ? containers.length
    : (supplier?.container_count ?? 0);
  const canDelete = !isLoading && containerCount === 0;

  return (
    <Dialog
      open={supplier !== null}
      onClose={onClose}
      fullWidth
      maxWidth="sm"
    >
      <DialogTitle>Delete supplier “{supplier?.name}”?</DialogTitle>
      <DialogContent>
        {isLoading && (
          <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
            <CircularProgress size={20} />
          </Box>
        )}

        {!isLoading && containerCount === 0 && (
          <Typography variant="body2">
            No containers reference this supplier. Safe to delete.
          </Typography>
        )}

        {!isLoading && containerCount > 0 && (
          <Stack spacing={1.5}>
            <Alert severity="warning">
              {containerCount} container{containerCount === 1 ? "" : "s"} still
              reference this supplier. Reassign each to another supplier (or
              clear) before deletion.
            </Alert>
            <Stack
              sx={{
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 1,
                overflow: "hidden",
              }}
            >
              {containerList.map((c, i) => (
                <Stack
                  key={c.id}
                  direction="row"
                  spacing={1}
                  sx={{
                    px: 1.5,
                    py: 1,
                    alignItems: "center",
                    borderBottom:
                      i < containerList.length - 1 ? "1px solid" : "none",
                    borderColor: "divider",
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                      {c.chemical_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {c.identifier} — {c.amount} {c.unit}
                      {c.is_archived ? " · archived" : ""}
                    </Typography>
                  </Box>
                  <ReassignSupplier
                    groupId={groupId}
                    containerId={c.id}
                    currentSupplierId={supplier!.id}
                    otherSuppliers={otherSuppliers}
                  />
                </Stack>
              ))}
            </Stack>
          </Stack>
        )}

        {removeErr && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {String(removeErr)}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={remove.isPending}>
          Cancel
        </Button>
        <Button
          color="error"
          variant="contained"
          onClick={confirmDelete}
          disabled={!canDelete || remove.isPending}
        >
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function ReassignSupplier({
  groupId,
  containerId,
  currentSupplierId,
  otherSuppliers,
}: {
  groupId: string;
  containerId: string;
  currentSupplierId: string;
  otherSuppliers: SupplierRead[];
}) {
  const queryClient = useQueryClient();
  const reassign = useMutation({
    mutationFn: (supplierId: string | null) =>
      client
        .patch(`/groups/${groupId}/containers/${containerId}`, {
          supplier_id: supplierId,
        })
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["suppliers", groupId, currentSupplierId, "containers"],
      });
      queryClient.invalidateQueries({ queryKey: ["suppliers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
    },
  });

  return (
    <Autocomplete<SupplierRead>
      size="small"
      options={otherSuppliers}
      getOptionLabel={(o) => o.name}
      disabled={reassign.isPending}
      onChange={(_e, value) => {
        if (value) reassign.mutate(value.id);
      }}
      sx={{ width: 220 }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={reassign.isPending ? "Saving…" : "Reassign to"}
          size="small"
        />
      )}
    />
  );
}
