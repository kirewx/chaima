import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { useCurrentUser } from "../api/hooks/useAuth";
import { useGroup } from "../components/GroupContext";
import type { StorageLocationNode } from "../types";

export interface StorageNavigation {
  loading: boolean;
  /** Roots the user is allowed to see. SU → buildings. User → rooms (flattened from all buildings). */
  visibleRoots: StorageLocationNode[];
  /** Full ancestor chain from a visible root to the current node (inclusive). Empty at the root view. */
  path: StorageLocationNode[];
  /** Currently-selected node, or null at root. */
  current: StorageLocationNode | null;
  /** Children to render in the child list. Equal to current.children when a node is selected, else visibleRoots. */
  children: StorageLocationNode[];
  /** Containers live here — render the ContainerGrid instead of StorageChildList. */
  isLeaf: boolean;
  /** The kind of child that should be added by the "+ Add ..." button below the list, or null if the user can't add here. */
  nextChildKind: "building" | "room" | "cabinet" | "shelf" | null;
}

function findPath(
  nodes: StorageLocationNode[],
  targetId: string,
  acc: StorageLocationNode[] = [],
): StorageLocationNode[] | null {
  for (const n of nodes) {
    const next = [...acc, n];
    if (n.id === targetId) return next;
    const found = findPath(n.children, targetId, next);
    if (found) return found;
  }
  return null;
}

const CHILD_KIND: Record<string, StorageNavigation["nextChildKind"]> = {
  building: "room",
  room: "cabinet",
  cabinet: "shelf",
  shelf: null, // shelves hold containers, not sub-locations
};

export function useStorageNavigation(): StorageNavigation {
  const { groupId } = useGroup();
  const { data: user } = useCurrentUser();
  const { locationId } = useParams<{ locationId?: string }>();
  const tree = useStorageTree(groupId);

  return useMemo<StorageNavigation>(() => {
    const all = tree.data ?? [];
    const isSuperuser = !!user?.is_superuser;

    // Non-SU: skip the building layer, present rooms as the visible roots.
    const visibleRoots: StorageLocationNode[] = isSuperuser
      ? all
      : all.flatMap((building) =>
          building.kind === "building" ? building.children : [building],
        );

    const path = locationId ? findPath(visibleRoots, locationId) ?? [] : [];
    const current = path.length ? path[path.length - 1] : null;
    const children = current ? current.children : visibleRoots;
    const isLeaf = current?.kind === "shelf";

    let nextChildKind: StorageNavigation["nextChildKind"];
    if (!current) {
      nextChildKind = isSuperuser ? "building" : "room";
    } else {
      nextChildKind = CHILD_KIND[current.kind] ?? null;
    }

    return {
      loading: tree.isLoading,
      visibleRoots,
      path,
      current,
      children,
      isLeaf,
      nextChildKind,
    };
  }, [tree.data, tree.isLoading, user?.is_superuser, locationId]);
}
