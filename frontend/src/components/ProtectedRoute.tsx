import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { CircularProgress, Box } from "@mui/material";
import { useCurrentUser } from "../api/hooks/useAuth";
import { useGroups } from "../api/hooks/useGroups";
import { useGroupOptional } from "./GroupContext";

export default function ProtectedRoute() {
  const { data: user, isLoading: userLoading, isError } = useCurrentUser();
  const { groupId, setGroupId } = useGroupOptional();
  const groupsQuery = useGroups();
  const location = useLocation();

  useEffect(() => {
    if (!groupId && groupsQuery.data && groupsQuery.data.length > 0) {
      setGroupId(groupsQuery.data[0].id);
    }
  }, [groupId, groupsQuery.data, setGroupId]);

  if (userLoading || groupsQuery.isLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "100vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (isError || !user) {
    return <Navigate to="/login" replace />;
  }

  if (
    !groupId &&
    groupsQuery.data?.length === 0 &&
    location.pathname !== "/settings"
  ) {
    return <Navigate to="/settings" replace />;
  }

  return <Outlet />;
}
