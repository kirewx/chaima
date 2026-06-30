import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Typography,
  Stack,
  Chip,
  Tooltip,
  Box,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import type { GHSCodeRead, PStatementRead } from "../types";
import { GHSPictogramRow } from "./GHSPictogramRow";
import { worstSignalWord } from "./hazardSignal";

interface Props {
  open: boolean;
  onClose: () => void;
  chemicalName: string;
  ghsCodes: GHSCodeRead[];
  pStatements: PStatementRead[];
}

export function HazardStatementsDialog({
  open,
  onClose,
  chemicalName,
  ghsCodes,
  pStatements,
}: Props) {
  const signal = worstSignalWord(ghsCodes);
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pr: 5 }}>
        Hazard &amp; precautionary statements
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block" }}
        >
          {chemicalName}
        </Typography>
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{ position: "absolute", right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {(ghsCodes.length > 0 || signal) && (
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}>
            {ghsCodes.length > 0 && (
              <GHSPictogramRow codes={ghsCodes} size={36} />
            )}
            {signal && (
              <Chip
                label={signal}
                size="small"
                color={signal === "Danger" ? "error" : "warning"}
                sx={{ fontWeight: 600 }}
              />
            )}
          </Stack>
        )}

        {ghsCodes.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              Hazard statements (H)
            </Typography>
            <Stack spacing={0.5}>
              {ghsCodes.map((c) => (
                <Typography key={c.id} variant="body2">
                  <strong>{c.code}</strong> — {c.description}
                </Typography>
              ))}
            </Stack>
          </Box>
        )}

        {pStatements.length > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              Precautionary statements (P)
            </Typography>
            <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.5 }}>
              {pStatements.map((p) => (
                <Tooltip key={p.id} title={p.description} arrow>
                  <Chip label={p.code} size="small" variant="outlined" />
                </Tooltip>
              ))}
            </Stack>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
