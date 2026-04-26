import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  PaginatedResponse,
  ProjectRead,
  ProjectCreate,
  ProjectUpdate,
} from "../../types";

export function useProjects(groupId: string, includeArchived: boolean = false) {
  return useQuery<PaginatedResponse<ProjectRead>>({
    queryKey: ["projects", groupId, { includeArchived }],
    queryFn: () =>
      client
        .get(`/groups/${groupId}/projects`, {
          params: { include_archived: includeArchived, limit: 500 },
        })
        .then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useCreateProject(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) =>
      client
        .post(`/groups/${groupId}/projects`, data)
        .then((r) => r.data as ProjectRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    },
  });
}

export function useUpdateProject(groupId: string, projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectUpdate) =>
      client
        .patch(`/groups/${groupId}/projects/${projectId}`, data)
        .then((r) => r.data as ProjectRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    },
  });
}

export function useArchiveProject(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) =>
      client
        .post(`/groups/${groupId}/projects/${projectId}/archive`)
        .then((r) => r.data as ProjectRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    },
  });
}
