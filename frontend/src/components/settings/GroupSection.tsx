import { Box, Stack, TextField, MenuItem, Typography, Alert, Chip } from "@mui/material";
import { SectionHeader } from "./SectionHeader";
import { useGroups } from "../../api/hooks/useGroups";
import { useCurrentUser, useUpdateMainGroup } from "../../api/hooks/useAuth";

export function GroupSection() {
  const { data: user } = useCurrentUser();
  const { data: groups = [], isLoading } = useGroups();
  const updateMain = useUpdateMainGroup();

  if (!user) return <SectionHeader title="Group" />;

  const current = groups.find((g) => g.id === user.main_group_id);
  const hasMultiple = groups.length > 1;

  return (
    <Box>
      <SectionHeader
        title="Group"
        subtitle="Your lab group determines which chemicals, containers, and storage you can see."
      />

      {groups.length === 0 && !isLoading && (
        <Alert severity="info">
          You are not a member of any group yet. Ask an admin for an invite.
        </Alert>
      )}

      {current && (
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography variant="h5">CURRENT</Typography>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography variant="h3">{current.name}</Typography>
              <Chip label="MAIN" size="small" color="primary" sx={{ fontSize: 10 }} />
            </Stack>
            {current.description && (
              <Typography variant="body2" color="text.secondary">
                {current.description}
              </Typography>
            )}
          </Stack>

          {hasMultiple && (
            <Stack spacing={1}>
              <Typography variant="h5">CHANGE MAIN GROUP</Typography>
              <TextField
                select
                size="small"
                value={user.main_group_id ?? ""}
                onChange={(e) => updateMain.mutate(e.target.value)}
                sx={{ maxWidth: 360 }}
                helperText="You will still see data from all groups you belong to, but this one will be the default."
              >
                {groups.map((g) => (
                  <MenuItem key={g.id} value={g.id}>
                    {g.name}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          )}

          {!hasMultiple && (
            <Typography variant="body2" color="text.secondary">
              You only belong to one group. When you join another, you'll be able to change your main group here.
            </Typography>
          )}
        </Stack>
      )}
    </Box>
  );
}
