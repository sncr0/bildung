import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getWorks,
  getWork,
  createWork,
  updateWork,
  type Work,
} from "../services/api";

export function useWorks(params?: { status?: string; author?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["works", params],
    queryFn: () => getWorks(params),
  });
}

export function useWork(id: string) {
  return useQuery({
    queryKey: ["works", id],
    queryFn: () => getWork(id),
    enabled: !!id,
  });
}

export function useCreateWork() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createWork,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works"] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
    },
  });
}

export function useUpdateWork(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Work>) => updateWork(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works"] });
      queryClient.invalidateQueries({ queryKey: ["works", id] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
