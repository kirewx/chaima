import { Box, Dialog, DialogContent, DialogTitle, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

interface Props {
  open: boolean;
  onClose: () => void;
  chemicalName: string;
  /** Raw SVG markup, from the cached useChemicalStructureSvg result. */
  svg: string;
}

/** Enlarged, losslessly scaled view of a chemical's structure SVG. */
export function StructureDialog({ open, onClose, chemicalName, svg }: Props) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md">
      <DialogTitle sx={{ pr: 6 }}>
        {chemicalName}
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{ position: "absolute", right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <Box
          sx={{
            width: "min(80vw, 70vh)",
            height: "min(80vw, 70vh)",
            color: "text.primary",
            "& svg": { width: "100%", height: "100%", display: "block" },
          }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </DialogContent>
    </Dialog>
  );
}
