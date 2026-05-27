import { useMutation } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import client from "../client";
import type { ExtractedLabel } from "../../types";
import { resizeImage } from "../../utils/imageResize";
import { useCurrentUser } from "./useAuth";

export function useExtractFromPhoto() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";

  return useMutation<ExtractedLabel, AxiosError, File>({
    mutationFn: async (file) => {
      const resized = await resizeImage(file);
      const form = new FormData();
      form.append("file", resized);
      const r = await client.post<ExtractedLabel>(
        `/groups/${groupId}/chemicals/extract-from-photo`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return r.data;
    },
  });
}
