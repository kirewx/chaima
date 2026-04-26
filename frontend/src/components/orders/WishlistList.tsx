import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Stack,
  Typography,
  Alert,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { useState } from "react";
import {
  useWishlist,
  useDismissWishlist,
  usePromoteWishlist,
} from "../../api/hooks/useWishlist";
import { useDrawer } from "../drawer/DrawerContext";
import { WishlistForm } from "./WishlistForm";

interface Props {
  groupId: string;
}

export function WishlistList({ groupId }: Props) {
  const { data, isLoading } = useWishlist(groupId);
  const dismiss = useDismissWishlist(groupId);
  const promote = usePromoteWishlist(groupId);
  const { open: openDrawer } = useDrawer();
  const [showForm, setShowForm] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  const items = data?.items ?? [];

  const handlePromote = async (wid: string) => {
    setPromoteError(null);
    try {
      const result = await promote.mutateAsync(wid);
      openDrawer({
        kind: "new-order",
        groupId,
        chemicalId: result.chemical_id,
        wishlistItemId: result.wishlist_item_id,
      });
    } catch (err) {
      const detail = (err as any).response?.data?.detail;
      setPromoteError(
        typeof detail === "object"
          ? detail.message
          : detail ?? "Could not resolve chemical via PubChem.",
      );
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <Box>
      <Stack direction="row" sx={{ mb: 2, justifyContent: "flex-end" }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setShowForm(true)}
        >
          Add to wishlist
        </Button>
      </Stack>

      {promoteError && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setPromoteError(null)}>
          {promoteError}
        </Alert>
      )}

      {items.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          Wishlist empty.
        </Typography>
      )}

      <Stack spacing={1}>
        {items.map((item) => (
          <Card key={item.id} variant="outlined">
            <CardContent>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2">
                    {item.chemical_name ??
                      `${item.freeform_name}${item.freeform_cas ? ` (${item.freeform_cas})` : ""}`}
                  </Typography>
                  {item.comment && (
                    <Typography variant="caption" color="text.secondary">
                      {item.comment}
                    </Typography>
                  )}
                </Box>
                <Button
                  size="small"
                  variant="outlined"
                  endIcon={<ArrowForwardIcon />}
                  onClick={() => handlePromote(item.id)}
                >
                  Promote
                </Button>
                <IconButton size="small" onClick={() => dismiss.mutate(item.id)}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>

      <WishlistForm
        open={showForm}
        groupId={groupId}
        onDone={() => setShowForm(false)}
      />
    </Box>
  );
}
