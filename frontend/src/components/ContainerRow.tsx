import { Box, Typography } from "@mui/material";
import LocationOnIcon from "@mui/icons-material/LocationOn";
import type { ContainerRead } from "../types";

interface ContainerRowProps {
  container: ContainerRead;
  locationPath?: string;
  supplierName?: string;
  expanded?: boolean;
}

export default function ContainerRow({ container, locationPath, supplierName, expanded = false }: ContainerRowProps) {
  return (
    <Box sx={{ bgcolor: "#111111", borderRadius: 1.5, p: 1, borderLeft: 3, borderColor: container.is_archived ? "text.secondary" : "success.main" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Box>
          <Typography variant="body2" component="span">
            <Typography component="span" variant="body2" color="success.main" fontWeight={600}>
              {container.amount} {container.unit}
            </Typography>
            {supplierName && (
              <>
                <Typography component="span" color="text.secondary"> &middot; </Typography>
                <Typography component="span" variant="body2" color="text.secondary">{supplierName}</Typography>
              </>
            )}
          </Typography>
          {expanded && (
            <Typography variant="caption" color="text.secondary" display="block">
              ID: {container.identifier}
              {container.purchased_at && ` · Purchased ${container.purchased_at}`}
            </Typography>
          )}
        </Box>
        {locationPath && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <LocationOnIcon sx={{ fontSize: 14, color: "primary.main" }} />
            <Typography variant="caption" color="primary.main">{locationPath}</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
