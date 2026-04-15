import { Breadcrumbs, Link, Typography, Box } from "@mui/material";
import { useNavigate } from "react-router-dom";
import type { StorageLocationNode } from "../types";

export interface StorageBreadcrumbsProps {
  path: StorageLocationNode[];
}

export function StorageBreadcrumbs({ path }: StorageBreadcrumbsProps) {
  const navigate = useNavigate();
  return (
    <Box sx={{ mb: 2 }}>
      <Breadcrumbs
        separator="›"
        sx={{
          fontSize: 13,
          "& .MuiBreadcrumbs-separator": { color: "text.secondary", mx: 0.75 },
        }}
      >
        <Link
          component="button"
          underline="hover"
          onClick={() => navigate("/storage")}
          sx={{ color: "text.secondary", fontSize: 13 }}
        >
          Storage
        </Link>
        {path.map((node, i) => {
          const isLast = i === path.length - 1;
          return isLast ? (
            <Typography key={node.id} sx={{ color: "text.primary", fontSize: 13, fontWeight: 500 }}>
              {node.name}
            </Typography>
          ) : (
            <Link
              key={node.id}
              component="button"
              underline="hover"
              onClick={() => navigate(`/storage/${node.id}`)}
              sx={{ color: "text.secondary", fontSize: 13 }}
            >
              {node.name}
            </Link>
          );
        })}
      </Breadcrumbs>
    </Box>
  );
}
