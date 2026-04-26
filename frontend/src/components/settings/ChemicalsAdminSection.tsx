import { useEffect, useMemo, useState } from "react";
import {
  Alert, Autocomplete, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  LinearProgress, Stack, TextField, Typography,
} from "@mui/material";
import ScienceIcon from "@mui/icons-material/Science";
import { SectionHeader } from "./SectionHeader";
import { useChemicals, useChemicalDetail } from "../../api/hooks/useChemicals";
import { useHazardTags } from "../../api/hooks/useHazardTags";
import { useGHSCodes } from "../../api/hooks/useGHSCodes";
import client from "../../api/client";
import type { ChemicalRead } from "../../types";

interface Props {
  groupId: string;
}

type EnrichEvent =
  | { id: string; name: string; status: "enriched" | "skipped" | "not_found" | "error" }
  | { summary: { enriched: number; skipped: number; not_found: number; error: number } };

export function ChemicalsAdminSection({ groupId }: Props) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<EnrichEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const start = async () => {
    setRunning(true);
    setEvents([]);
    setErr(null);
    try {
      const resp = await fetch(`/api/v1/groups/${groupId}/chemicals/enrich-pubchem`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chemical_ids: null }),
        credentials: "include",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n");
        buf = parts.pop()!;
        for (const line of parts) {
          if (!line.startsWith("data: ")) continue;
          const ev = JSON.parse(line.slice(6)) as EnrichEvent;
          setEvents((prev) => [...prev, ev]);
        }
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const summary = events.find((e) => "summary" in e) as
    | { summary: { enriched: number; skipped: number; not_found: number; error: number } }
    | undefined;
  const perChemCount = events.filter((e) => "id" in e).length;

  return (
    <Box>
      <SectionHeader
        title="Chemicals"
        subtitle="Bulk maintenance operations for this group's chemical database."
      />
      <Stack spacing={2} sx={{ maxWidth: 600 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Button
            variant="contained"
            size="small"
            startIcon={<ScienceIcon />}
            onClick={() => setOpen(true)}
          >
            Enrich missing data from PubChem
          </Button>
          <Typography variant="body2" color="text.secondary">
            Fills SMILES, molar mass, CAS, CID for chemicals that lack them.
          </Typography>
        </Stack>
      </Stack>

      <Dialog open={open} onClose={() => !running && setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Enrich chemicals from PubChem</DialogTitle>
        <DialogContent>
          {!running && !summary && (
            <Typography>This fetches missing data from PubChem for every chemical in this group that has no CID yet. Takes ~0.25s per chemical.</Typography>
          )}
          {running && (
            <Stack spacing={2}>
              <LinearProgress />
              <Typography variant="body2">{perChemCount} processed…</Typography>
            </Stack>
          )}
          {summary && (
            <Alert severity="success">
              Enriched {summary.summary.enriched}, skipped {summary.summary.skipped},
              not found {summary.summary.not_found}, errors {summary.summary.error}.
            </Alert>
          )}
          {err && <Alert severity="error">{err}</Alert>}
        </DialogContent>
        <DialogActions>
          {!running && !summary && (
            <>
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="contained" onClick={start}>Start</Button>
            </>
          )}
          {(running || summary) && (
            <Button onClick={() => { setOpen(false); setEvents([]); }} disabled={running}>Close</Button>
          )}
        </DialogActions>
      </Dialog>

      <AssignHazardsDebug groupId={groupId} />
    </Box>
  );
}

function AssignHazardsDebug({ groupId }: { groupId: string }) {
  const [chemId, setChemId] = useState<string | null>(null);
  const [chemQuery, setChemQuery] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [ghsIds, setGhsIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const chemicals = useChemicals(groupId, { search: chemQuery, limit: 20 });
  const tags = useHazardTags(groupId);
  const ghs = useGHSCodes();
  const detail = useChemicalDetail(groupId, chemId ?? "");

  const chemicalOptions = useMemo<ChemicalRead[]>(() => {
    const pages = chemicals.data?.pages ?? [];
    return pages.flatMap((p) => p.items);
  }, [chemicals.data]);

  useEffect(() => {
    if (detail.data) {
      setTagIds(detail.data.hazard_tags?.map((t) => t.id) ?? []);
      setGhsIds(detail.data.ghs_codes?.map((g) => g.id) ?? []);
    } else {
      setTagIds([]);
      setGhsIds([]);
    }
  }, [detail.data?.id]);

  const onSave = async () => {
    if (!chemId) return;
    setBusy(true);
    setMsg(null);
    try {
      await Promise.all([
        client.put(`/groups/${groupId}/chemicals/${chemId}/hazard-tags`, {
          hazard_tag_ids: tagIds,
        }),
        client.put(`/groups/${groupId}/chemicals/${chemId}/ghs-codes`, {
          ghs_ids: ghsIds,
        }),
      ]);
      setMsg({ kind: "ok", text: "Saved." });
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box id="assign-hazards-debug" sx={{ mt: 4 }}>
      <SectionHeader
        title="Assign hazards (debug)"
        subtitle="Admin-only. Attaches GHS codes and hazard tags to a chemical without going through the regular drawer."
      />
      <Stack spacing={2} sx={{ maxWidth: 600 }}>
        <Autocomplete
          size="small"
          options={chemicalOptions}
          getOptionLabel={(c) => c.name}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          inputValue={chemQuery}
          onInputChange={(_, v) => setChemQuery(v)}
          onChange={(_, c) => setChemId(c?.id ?? null)}
          renderInput={(params) => (
            <TextField {...params} label="Chemical" placeholder="Type to search" />
          )}
        />

        {chemId && (
          <>
            <Autocomplete
              multiple
              size="small"
              options={tags.data?.items ?? []}
              getOptionLabel={(t) => t.name}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={(tags.data?.items ?? []).filter((t) => tagIds.includes(t.id))}
              onChange={(_, vs) => setTagIds(vs.map((t) => t.id))}
              renderInput={(params) => <TextField {...params} label="Hazard tags" />}
            />
            <Autocomplete
              multiple
              size="small"
              options={ghs.data ?? []}
              getOptionLabel={(g) => `${g.code} - ${g.description}`}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={(ghs.data ?? []).filter((g) => ghsIds.includes(g.id))}
              onChange={(_, vs) => setGhsIds(vs.map((g) => g.id))}
              renderInput={(params) => <TextField {...params} label="GHS codes" />}
            />
            {msg && (
              <Alert severity={msg.kind === "ok" ? "success" : "error"}>
                {msg.text}
              </Alert>
            )}
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                size="small"
                disabled={busy}
                onClick={onSave}
              >
                {busy ? "Saving..." : "Save"}
              </Button>
            </Stack>
          </>
        )}
      </Stack>
    </Box>
  );
}
