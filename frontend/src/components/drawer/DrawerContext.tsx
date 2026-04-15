import { createContext, useContext, useState, type ReactNode } from "react";
import type { StorageKind } from "../../types";

export type DrawerConfig =
  | { kind: "chemical-new" }
  | { kind: "chemical-edit"; chemicalId: string }
  | { kind: "container-new"; chemicalId: string }
  | { kind: "container-edit"; containerId: string }
  | { kind: "storage-new"; childKind: StorageKind; parentId: string | null }
  | { kind: "storage-edit"; locationId: string }
  | null;

interface Ctx {
  config: DrawerConfig;
  open: (c: Exclude<DrawerConfig, null>) => void;
  close: () => void;
}

const DrawerCtx = createContext<Ctx | null>(null);

export function DrawerProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<DrawerConfig>(null);
  return (
    <DrawerCtx.Provider
      value={{
        config,
        open: setConfig,
        close: () => setConfig(null),
      }}
    >
      {children}
    </DrawerCtx.Provider>
  );
}

export function useDrawer() {
  const v = useContext(DrawerCtx);
  if (!v) throw new Error("useDrawer must be used inside a DrawerProvider");
  return v;
}
