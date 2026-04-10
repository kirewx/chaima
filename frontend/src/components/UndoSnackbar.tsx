import { Snackbar, Button, Alert } from "@mui/material";

interface UndoSnackbarProps {
  open: boolean;
  message: string;
  onUndo: () => void;
  onClose: () => void;
  autoHideDuration?: number;
}

export default function UndoSnackbar({ open, message, onUndo, onClose, autoHideDuration = 5000 }: UndoSnackbarProps) {
  return (
    <Snackbar open={open} autoHideDuration={autoHideDuration} onClose={onClose} anchorOrigin={{ vertical: "bottom", horizontal: "center" }} sx={{ mb: 7 }}>
      <Alert severity="success" variant="filled" action={<Button color="inherit" size="small" onClick={onUndo}>Undo</Button>} onClose={onClose}>
        {message}
      </Alert>
    </Snackbar>
  );
}
