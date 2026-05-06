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
  /** Parent id to use when the "+ Add ..." button is clicked. For non-SU at root creating a room, this is the implicit building derived from the tree. Null at the SU root view (buildings are top-level) or when the parent is the currently-selected node. */
  nextChildParentId: string | null;
  /** If non-null, the "+ Add ..." action is blocked with this human-readable reason (used for tooltip + disabled state). */
  nextChildDisabledReason: string | null;
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

    let nextChildParentId: string | null = current?.id ?? null;
    let nextChildDisabledReason: string | null = null;

    if (!current && nextChildKind === "room") {
      // Non-SU adding a room at the root view: the parent must be the
      // group's building. We derive it from the unflattened tree.
      const buildings = all.filter((n) => n.kind === "building");
      if (buildings.length === 1) {
        nextChildParentId = buildings[0].id;
      } else if (buildings.length === 0) {
        nextChildParentId = null;
        nextChildDisabledReason =
          "No building is set up for your group yet. Ask a superuser to create one.";
      } else {
        nextChildParentId = null;
        nextChildDisabledReason =
          "Your group is linked to multiple buildings. Ask a superuser to clarify which one to use.";
      }
    }

    return {
      loading: tree.isLoading,
      visibleRoots,
      path,
      current,
      children,
      isLeaf,
      nextChildKind,
      nextChildParentId,
      nextChildDisabledReason,
    };
  }, [tree.data, tree.isLoading, user?.is_superuser, locationId]);
}
