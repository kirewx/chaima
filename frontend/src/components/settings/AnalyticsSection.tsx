import { useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
} from "@mui/material";
import type { SelectChangeEvent } from "@mui/material";
import { SectionHeader } from "./SectionHeader";
import {
  useAnalyticsSummary,
  useAnalyticsUsers,
} from "../../api/hooks/useAdminAnalytics";
import type { AnalyticsRange, UserStatsRow } from "../../types";

const RANGE_OPTIONS: { value: AnalyticsRange; label: string }[] = [
  { value: "24h", label: "Letzte 24h" },
  { value: "7d", label: "Letzte 7 Tage" },
  { value: "30d", label: "Letzte 30 Tage" },
  { value: "90d", label: "Letzte 90 Tage" },
];

type UserSortField = "email" | "last_login_at" | "logins_in_range" | "searches" | "chemicals_created" | "containers_created" | "photo_extracts";

export function AnalyticsSection() {
  const [range, setRange] = useState<AnalyticsRange>("7d");
  const [sortField, setSortField] = useState<UserSortField>("last_login_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const summary = useAnalyticsSummary(range);
  const users = useAnalyticsUsers(range);

  const onRangeChange = (e: SelectChangeEvent<AnalyticsRange>) => {
    setRange(e.target.value as AnalyticsRange);
  };

  const handleSort = (field: UserSortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortedUsers = sortUsers(users.data ?? [], sortField, sortDir);

  return (
    <Box>
      <SectionHeader
        title="Analytics"
        subtitle="Nutzungs- und Performance-Daten dieser Instanz. Superuser-only."
      />

      <Stack spacing={2}>
        <Box>
          <Select<AnalyticsRange>
            size="small"
            value={range}
            onChange={onRangeChange}
            sx={{ minWidth: 200 }}
          >
            {RANGE_OPTIONS.map((o) => (
              <MenuItem key={o.value} value={o.value}>
                {o.label}
              </MenuItem>
            ))}
          </Select>
        </Box>

        {summary.isError && (
          <Alert severity="error">
            Konnte Summary nicht laden — bitte neu laden.
          </Alert>
        )}

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: {
              xs: "1fr 1fr",
              md: "repeat(4, 1fr)",
            },
          }}
        >
          <KpiCard
            label="Aktive User"
            value={summary.data?.active_users}
            loading={summary.isLoading}
          />
          <KpiCard
            label="Logins"
            value={summary.data?.total_logins}
            loading={summary.isLoading}
          />
          <KpiCard
            label="Suchen"
            value={summary.data?.total_searches}
            loading={summary.isLoading}
          />
          <KpiCard
            label="Foto-Extract"
            value={summary.data?.total_photo_extracts}
            loading={summary.isLoading}
          />
        </Box>

        <Box>
          <Typography variant="h5" sx={{ mb: 1 }}>
            Per User
          </Typography>
          {users.isError && (
            <Alert severity="error">
              Konnte User-Liste nicht laden.
            </Alert>
          )}
          {users.isLoading ? (
            <Stack spacing={1}>
              <Skeleton height={32} />
              <Skeleton height={32} />
              <Skeleton height={32} />
            </Stack>
          ) : sortedUsers.length === 0 ? (
            <Typography color="text.secondary">
              Keine User im Zeitraum aktiv.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <SortHeader field="email" current={sortField} dir={sortDir} onClick={handleSort}>
                    User
                  </SortHeader>
                  <SortHeader field="last_login_at" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Last seen
                  </SortHeader>
                  <SortHeader field="logins_in_range" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Logins
                  </SortHeader>
                  <SortHeader field="searches" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Suchen
                  </SortHeader>
                  <SortHeader field="chemicals_created" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Chemicals
                  </SortHeader>
                  <SortHeader field="containers_created" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Container
                  </SortHeader>
                  <SortHeader field="photo_extracts" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Foto
                  </SortHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedUsers.map((row) => (
                  <TableRow key={row.user_id}>
                    <TableCell>{row.email}</TableCell>
                    <TableCell align="right">{formatLastSeen(row.last_login_at)}</TableCell>
                    <TableCell align="right">{row.logins_in_range}</TableCell>
                    <TableCell align="right">{row.searches}</TableCell>
                    <TableCell align="right">{row.chemicals_created}</TableCell>
                    <TableCell align="right">{row.containers_created}</TableCell>
                    <TableCell align="right">{row.photo_extracts}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Box>
      </Stack>
    </Box>
  );
}

function KpiCard({ label, value, loading }: { label: string; value: number | undefined; loading: boolean }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        {loading ? (
          <Skeleton width={60} height={36} />
        ) : (
          <Typography variant="h3">{value ?? 0}</Typography>
        )}
      </CardContent>
    </Card>
  );
}

function SortHeader({
  field, current, dir, onClick, children, align,
}: {
  field: UserSortField;
  current: UserSortField;
  dir: "asc" | "desc";
  onClick: (f: UserSortField) => void;
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <TableCell align={align ?? "left"}>
      <TableSortLabel
        active={current === field}
        direction={current === field ? dir : "desc"}
        onClick={() => onClick(field)}
      >
        {children}
      </TableSortLabel>
    </TableCell>
  );
}

function sortUsers(rows: UserStatsRow[], field: UserSortField, dir: "asc" | "desc"): UserStatsRow[] {
  const out = [...rows];
  out.sort((a, b) => {
    const av = a[field];
    const bv = b[field];
    // last_login_at: null sorts last regardless of dir.
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (typeof av === "string" && typeof bv === "string") {
      return dir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return dir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
  });
  return out;
}

function formatLastSeen(iso: string | null): string {
  if (!iso) return "nie";
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "gerade eben";
  if (diffMin < 60) return `vor ${diffMin}min`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `vor ${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `vor ${diffDay}d`;
  return date.toLocaleDateString();
}
