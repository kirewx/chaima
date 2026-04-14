import { Typography } from "@mui/material";

interface Props {
  chemicalId?: string;
  onDone: () => void;
}

export function ChemicalForm({ chemicalId, onDone: _onDone }: Props) {
  return (
    <Typography variant="body2" color="text.secondary">
      ChemicalForm stub — Task 12 will implement this.
      {chemicalId ? ` Editing ${chemicalId}.` : " Creating new chemical."}
    </Typography>
  );
}
