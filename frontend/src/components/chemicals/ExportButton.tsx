import { useState } from "react";
import { Button, Menu, MenuItem } from "@mui/material";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import client from "../../api/client";
import type { ChemicalSearchParams } from "../../types";

interface Props {
  groupId: string;
  params: ChemicalSearchParams;
  includeArchived: boolean;
}

export function ExportButton({ groupId, params, includeArchived }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);

  const download = async (fmt: "csv" | "xlsx") => {
    setAnchor(null);
    setBusy(true);
    try {
      const resp = await client.get(
        `/groups/${groupId}/chemicals/export`,
        {
          params: { ...params, include_archived: includeArchived, format: fmt },
          responseType: "blob",
        },
      );
      const cd = resp.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename="([^"]+)"/);
      const filename = match?.[1] ?? `chaima-export.${fmt}`;
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        startIcon={<FileDownloadIcon />}
        disabled={busy}
        onClick={(e) => setAnchor(e.currentTarget)}
      >
        Export
      </Button>
      <Menu
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
      >
        <MenuItem onClick={() => download("csv")}>CSV</MenuItem>
        <MenuItem onClick={() => download("xlsx")}>Excel</MenuItem>
      </Menu>
    </>
  );
}
