import Box from "@mui/material/Box";
import type { SxProps, Theme } from "@mui/material/styles";

/** Brand purple from the logo design (design/assets), light/dark variants. */
const BRACKET = { light: "#6A4BC4", dark: "#9B84E8" } as const;

/** The `[chaima]` wordmark: mono font, purple brackets, matches the logo. */
export function Wordmark({ sx }: { sx?: SxProps<Theme> }) {
  return (
    <Box
      component="span"
      sx={[
        {
          fontFamily: '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace',
          fontWeight: 500,
          color: "text.primary",
          "& .bracket": {
            color: (t: Theme) => (t.palette.mode === "dark" ? BRACKET.dark : BRACKET.light),
          },
        },
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      <span className="bracket">[</span>chaima<span className="bracket">]</span>
    </Box>
  );
}
