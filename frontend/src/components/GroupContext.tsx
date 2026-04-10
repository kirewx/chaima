import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useCurrentUser, useUpdateMainGroup } from "../api/hooks/useAuth";

interface GroupContextValue {
  groupId: string | null;
  setGroupId: (id: string) => void;
}

const GroupContext = createContext<GroupContextValue>({
  groupId: null,
  setGroupId: () => {},
});

export function GroupProvider({ children }: { children: ReactNode }) {
  const { data: user } = useCurrentUser();
  const updateMainGroup = useUpdateMainGroup();

  const groupId = user?.main_group_id ?? null;

  const setGroupId = (id: string) => {
    updateMainGroup.mutate(id);
  };

  useEffect(() => {
    localStorage.removeItem("chaima_group_id");
  }, []);

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
