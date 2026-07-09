import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useCreateWishlist } from "../../api/hooks/useWishlist";
import { errorMessage } from "../../utils/errorMessage";

interface Props {
  open: boolean;
  groupId: string;
  onDone: () => void;
}

export function WishlistForm({ open, groupId, onDone }: Props) {
  const create = useCreateWishlist(groupId);
  const [freeformName, setFreeformName] = useState("");
  const [freeformCas, setFreeformCas] = useState("");
  const [comment, setComment] = useState("");

  // Reset stale mutation errors when the dialog (re)opens.
  useEffect(() => {
    if (open) create.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = async () => {
    try {
      await create.mutateAsync({
        freeform_name: freeformName.trim(),
        freeform_cas: freeformCas.trim() || null,
        comment: comment.trim() || null,
      });
    } catch {
      return; // surfaced via create.error below
    }
    onDone();
    setFreeformName("");
    setFreeformCas("");
    setComment("");
  };

  return (
    <Dialog open={open} onClose={onDone} fullWidth maxWidth="xs">
      <DialogTitle>Add to wishlist</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField
            autoFocus
            label="Chemical name"
            value={freeformName}
            onChange={(e) => setFreeformName(e.target.value)}
            size="small"
          />
          <TextField
            label="CAS (optional)"
            value={freeformCas}
            onChange={(e) => setFreeformCas(e.target.value)}
            size="small"
          />
          <TextField
            label="Comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            multiline
            rows={2}
            size="small"
          />
          <Typography variant="caption" color="text.secondary">
            Promote a wishlist item later to convert it into a real order.
          </Typography>
          {create.error != null && (
            <Alert severity="error">{errorMessage(create.error)}</Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onDone}>Cancel</Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!freeformName.trim() || create.isPending}
        >
          Add
        </Button>
      </DialogActions>
    </Dialog>
  );
}
