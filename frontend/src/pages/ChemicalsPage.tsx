import { Box, TextField, InputAdornment, IconButton, Stack } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import TuneIcon from "@mui/icons-material/Tune";
import { useState } from "react";
import { useChemicals } from "../api/hooks/useChemicals";
import { useCurrentUser } from "../api/hooks/useAuth";
import { ChemicalList } from "../components/ChemicalList";

export default function ChemicalsPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? undefined;
  const [search, setSearch] = useState("");

  const { data, isLoading } = useChemicals(groupId as string, { search: search || undefined }, false);

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  if (!groupId) {
    return <Box sx={{ color: "text.secondary" }}>No group selected.</Box>;
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Search chemical, CAS or container ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <IconButton
          aria-label="Filters"
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
          }}
        >
          <TuneIcon fontSize="small" />
        </IconButton>
      </Stack>
      <ChemicalList items={items} loading={isLoading} />
    </Stack>
  );
}
