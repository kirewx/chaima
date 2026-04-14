import { useMemo } from "react";
import { createAppTheme } from "../theme";
import { useCurrentUser } from "../api/hooks/useAuth";

export function useAppTheme() {
  const { data: user } = useCurrentUser();
  const mode = user?.dark_mode ? "dark" : "light";
  return useMemo(() => createAppTheme(mode), [mode]);
}
