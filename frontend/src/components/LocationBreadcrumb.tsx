import { Box } from "@mui/material";

interface Props {
  /** Path segments root → leaf, building level already filtered out. */
  names: string[];
}

/** Breadcrumb-style location path: dimmed parents, bold leaf. */
export function LocationBreadcrumb({ names }: Props) {
  if (names.length === 0) return <>—</>;
  const parents = names.slice(0, -1);
  const leaf = names[names.length - 1];
  return (
    <Box component="span">
      {parents.map((name, i) => (
        <Box component="span" key={i} sx={{ color: "text.secondary" }}>
          {name}
          <Box component="span" sx={{ color: "text.disabled" }}>
            {" › "}
          </Box>
        </Box>
      ))}
      <Box component="span" sx={{ color: "text.primary", fontWeight: 600 }}>
        {leaf}
      </Box>
    </Box>
  );
}
