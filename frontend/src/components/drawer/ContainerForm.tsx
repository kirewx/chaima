import { Typography } from "@mui/material";

interface Props {
  chemicalId?: string;
  containerId?: string;
  onDone: () => void;
}

export function ContainerForm({ chemicalId, containerId, onDone: _onDone }: Props) {
  return (
    <Typography variant="body2" color="text.secondary">
      ContainerForm stub — Task 13 will implement this.
      {containerId
        ? ` Editing container ${containerId}.`
        : ` Creating container for chemical ${chemicalId}.`}
    </Typography>
  );
}
