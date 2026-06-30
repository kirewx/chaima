import type { GHSCodeRead } from "../types";

export function worstSignalWord(
  codes: GHSCodeRead[],
): "Danger" | "Warning" | null {
  let hasWarning = false;
  for (const c of codes) {
    if (c.signal_word === "Danger") return "Danger";
    if (c.signal_word === "Warning") hasWarning = true;
  }
  return hasWarning ? "Warning" : null;
}
