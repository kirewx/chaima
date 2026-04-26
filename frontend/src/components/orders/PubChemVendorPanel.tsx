import {
  Alert,
  Box,
  Button,
  Collapse,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { usePubChemVendors } from "../../api/hooks/usePubChemVendors";

interface Props {
  cid: string;
  onPick: (vendorName: string) => void;
}

export function PubChemVendorPanel({ cid, onPick }: Props) {
  const { data, isLoading, error } = usePubChemVendors(cid);
  const [expanded, setExpanded] = useState(false);

  return (
    <Box>
      <Button
        size="small"
        variant="text"
        onClick={() => setExpanded((e) => !e)}
      >
        {expanded ? "Hide" : "Show"} PubChem vendor list
      </Button>

      <Collapse in={expanded}>
        {isLoading && <Typography variant="caption">Loading…</Typography>}
        {error && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            PubChem temporarily unavailable.
          </Alert>
        )}
        {data && data.vendors.length === 0 && (
          <Typography variant="caption" color="text.secondary">
            PubChem has no vendor list for this compound.
          </Typography>
        )}
        {data && data.vendors.length > 0 && (
          <Stack spacing={0.5} sx={{ mt: 1 }}>
            {data.vendors.map((v) => (
              <Stack
                key={v.url}
                direction="row"
                spacing={1}
                sx={{ alignItems: "center" }}
              >
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => onPick(v.name)}
                >
                  Use as supplier
                </Button>
                <Link href={v.url} target="_blank" rel="noopener" sx={{ flex: 1 }} noWrap>
                  {v.name}
                </Link>
              </Stack>
            ))}
          </Stack>
        )}
      </Collapse>
    </Box>
  );
}
