import { useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  ImportPreviewResponse,
  ImportCommitBody,
  ImportCommitResponse,
} from "../../types";

export function useImportPreview(groupId: string) {
  return useMutation<ImportPreviewResponse, unknown, { file: File; sheetName?: string }>({
    mutationFn: async ({ file, sheetName }) => {
      const form = new FormData();
      form.append("file", file);
      if (sheetName) form.append("sheet_name", sheetName);
      const resp = await client.post(
        `/groups/${groupId}/import/preview`, form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return resp.data;
    },
  });
}

export function useImportCommit(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation<ImportCommitResponse, unknown, ImportCommitBody>({
    mutationFn: (body) =>
      client.post(`/groups/${groupId}/import/commit`, body).then((r) => r.data),
    onSuccess: () => {
      // The import creates chemicals, containers and storage locations.
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] });
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] });
    },
  });
}
