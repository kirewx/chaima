import type { StorageLocationNode } from "../types";

/**
 * Depth-first walk of the storage tree returning the node chain
 * root → target (inclusive), or null when the id is not in the tree.
 */
export function findLocationTrail(
  nodes: StorageLocationNode[],
  targetId: string,
  trail: StorageLocationNode[] = [],
): StorageLocationNode[] | null {
  for (const n of nodes) {
    const next = [...trail, n];
    if (n.id === targetId) return next;
    const found = findLocationTrail(n.children, targetId, next);
    if (found) return found;
  }
  return null;
}

/**
 * Display rule for container cards: drop building levels. If that leaves
 * nothing (container attached at building level), keep the full trail so
 * the display is never empty.
 */
export function displayTrail(
  trail: StorageLocationNode[],
): StorageLocationNode[] {
  const filtered = trail.filter((n) => n.kind !== "building");
  return filtered.length > 0 ? filtered : trail;
}
