import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

interface GroupContextValue {
  groupId: string | null;
  setGroupId: (id: string) => void;
}

const GroupContext = createContext<GroupContextValue>({
  groupId: null,
  setGroupId: () => {},
});

export function GroupProvider({ children }: { children: ReactNode }) {
  const [groupId, setGroupIdState] = useState<string | null>(() =>
    localStorage.getItem("chaima_group_id"),
  );
  const queryClient = useQueryClient();

  const setGroupId = useCallback(
    (id: string) => {
      localStorage.setItem("chaima_group_id", id);
      setGroupIdState(id);
      queryClient.clear();
    },
    [queryClient],
  );

  return (
    <GroupContext.Provider value={{ groupId, setGroupId }}>
      {children}
    </GroupContext.Provider>
  );
}

export function useGroup() {
  const ctx = useContext(GroupContext);
  if (!ctx.groupId) {
    throw new Error("No active group selected");
  }
  return { groupId: ctx.groupId, setGroupId: ctx.setGroupId };
}

export function useGroupOptional() {
  return useContext(GroupContext);
}
