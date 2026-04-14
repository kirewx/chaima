import type { ReactNode } from "react";
import { useCurrentUser } from "../api/hooks/useAuth";

type Role = "admin" | "superuser" | "creator";

interface Props {
  allow: Role[];
  creatorId?: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export function RoleGate({ allow, creatorId, children, fallback = null }: Props) {
  const { data: user } = useCurrentUser();

  if (!user) return <>{fallback}</>;

  if (allow.includes("superuser") && user.is_superuser) {
    return <>{children}</>;
  }

  if (allow.includes("creator") && creatorId && user.id === creatorId) {
    return <>{children}</>;
  }

  // v1: every authenticated group member is treated as "admin".
  // When real group roles land, gate this on user.is_admin or similar.
  if (allow.includes("admin")) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
}
