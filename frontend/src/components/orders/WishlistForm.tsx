import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useCreateWishlist } from "../../api/hooks/useWishlist";

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

  const submit = async () => {
    await create.mutateAsync({
      freeform_name: freeformName,
      freeform_cas: freeformCas || null,
      comment: comment || null,
    });
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
