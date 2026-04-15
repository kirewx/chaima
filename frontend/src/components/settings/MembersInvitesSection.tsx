import { useState } from "react";
import {
  Box,
  Stack,
  Tabs,
  Tab,
  Button,
  IconButton,
  Typography,
  Chip,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Snackbar,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import AddIcon from "@mui/icons-material/Add";
import { SectionHeader } from "./SectionHeader";
import { useGroup, useGroupMembers, useUpdateMember, useRemoveMember } from "../../api/hooks/useGroups";
import { useGroupInvites, useCreateInvite, useRevokeInvite } from "../../api/hooks/useInvites";
import type { MemberRead } from "../../types";

interface Props {
  groupId: string;
}

export function MembersInvitesSection({ groupId }: Props) {
  const [tab, setTab] = useState<"members" | "invites">("members");
  const group = useGroup(groupId);
  const members = useGroupMembers(groupId);

  return (
    <Box>
      <SectionHeader
        title="Members & Invites"
        subtitle={group.data ? `${group.data.name} · ${members.data?.length ?? 0} members` : undefined}
      />
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ borderBottom: "1px solid", borderColor: "divider", mb: 2 }}
      >
        <Tab value="members" label="Members" />
        <Tab value="invites" label="Pending invites" />
      </Tabs>
      {tab === "members" && <MembersTab groupId={groupId} members={members.data ?? []} />}
      {tab === "invites" && <InvitesTab groupId={groupId} />}
    </Box>
  );
}

function MembersTab({ groupId, members }: { groupId: string; members: MemberRead[] }) {
  if (members.length === 0) {
    return <Typography variant="body2" color="text.secondary">No members yet.</Typography>;
  }
  return (
    <Stack
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        overflow: "hidden",
        bgcolor: "background.paper",
      }}
    >
      {members.map((m, i) => (
        <MemberRow
          key={m.user_id}
          groupId={groupId}
          member={m}
          divider={i < members.length - 1}
        />
      ))}
    </Stack>
  );
}

function MemberRow({
  groupId,
  member,
  divider,
}: {
  groupId: string;
  member: MemberRead;
  divider: boolean;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const update = useUpdateMember(groupId, member.user_id);
  const remove = useRemoveMember(groupId);
  const close = () => setAnchor(null);

  return (
    <Stack
      direction="row"
      sx={{
        px: 2,
        py: 1.25,
        gap: 2,
        alignItems: "center",
        borderBottom: divider ? "1px solid" : "none",
        borderColor: "divider",
      }}
    >
      <Box
        sx={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          bgcolor: "action.selected",
          color: "text.secondary",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        {member.email[0]?.toUpperCase() ?? "?"}
      </Box>
      <Typography variant="body1" sx={{ flex: 1, minWidth: 0 }} noWrap>
        {member.email}
      </Typography>
      <Chip
        label={member.is_admin ? "Admin" : "User"}
        size="small"
        sx={{
          bgcolor: member.is_admin ? "primary.light" : "action.selected",
          color: member.is_admin ? "primary.dark" : "text.secondary",
          fontSize: 10,
          height: 20,
        }}
      />
      <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)} aria-label="Member actions">
        <MoreHorizIcon fontSize="small" />
      </IconButton>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={close}>
        <MenuItem
          onClick={async () => {
            await update.mutateAsync({ is_admin: !member.is_admin });
            close();
          }}
        >
          {member.is_admin ? "Demote to user" : "Promote to admin"}
        </MenuItem>
        <MenuItem
          onClick={async () => {
            if (window.confirm(`Remove ${member.email} from the group?`)) {
              await remove.mutateAsync(member.user_id);
            }
            close();
          }}
        >
          Remove from group
        </MenuItem>
      </Menu>
    </Stack>
  );
}

function InvitesTab({ groupId }: { groupId: string }) {
  const invites = useGroupInvites(groupId);
  const create = useCreateInvite(groupId);
  const revoke = useRevokeInvite();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [lastToken, setLastToken] = useState<string | null>(null);
  const [toast, setToast] = useState(false);

  const handleGenerate = () => {
    create.mutate(undefined, {
      onSuccess: (data) => {
        setLastToken(data.token);
      },
    });
    setDialogOpen(true);
  };

  const copyUrl = (token: string) => {
    const url = `${window.location.origin}/invite/${token}`;
    void navigator.clipboard.writeText(url);
    setToast(true);
  };

  const rows = invites.data ?? [];

  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ justifyContent: "flex-end" }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={handleGenerate}
          disabled={create.isPending}
        >
          New invite
        </Button>
      </Stack>

      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No pending invites.
        </Typography>
      ) : (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {rows.map((inv, i) => (
            <Stack
              key={inv.id}
              direction="row"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                alignItems: "center",
                borderBottom: i < rows.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                  flex: 1,
                  minWidth: 0,
                }}
                noWrap
              >
                …{inv.token.slice(-12)}
              </Typography>
              <IconButton size="small" onClick={() => copyUrl(inv.token)} aria-label="Copy invite link">
                <ContentCopyIcon fontSize="small" />
              </IconButton>
              <Button
                size="small"
                color="error"
                onClick={() => revoke.mutate(inv.id)}
                disabled={revoke.isPending}
              >
                Revoke
              </Button>
            </Stack>
          ))}
        </Stack>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>New invite link</DialogTitle>
        <DialogContent>
          {create.isPending && <Typography variant="body2">Generating…</Typography>}
          {create.error instanceof Error && (
            <Alert severity="error">{create.error.message}</Alert>
          )}
          {lastToken && (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Share this link. It is valid once.
              </Typography>
              <TextField
                size="small"
                fullWidth
                value={`${window.location.origin}/invite/${lastToken}`}
                slotProps={{ input: { readOnly: true, sx: { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 } } }}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {lastToken && (
            <Button onClick={() => copyUrl(lastToken)} startIcon={<ContentCopyIcon />}>
              Copy
            </Button>
          )}
          <Button
            variant="contained"
            onClick={() => {
              setDialogOpen(false);
              setLastToken(null);
            }}
          >
            Done
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={toast}
        autoHideDuration={2000}
        onClose={() => setToast(false)}
        message="Copied to clipboard"
      />
    </Stack>
  );
}
