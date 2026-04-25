import { useState } from "react";
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  LinearProgress, Stack, Typography,
} from "@mui/material";
import ScienceIcon from "@mui/icons-material/Science";
import { SectionHeader } from "./SectionHeader";

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
              <Typography variant="body2">{perChemCount} processed\u2026</Typography>
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
    </Box>
  );
}
