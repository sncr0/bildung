import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getStreams,
  getStream,
  createStream,
  updateStream,
  deleteStream,
  addToStream,
  removeFromStream,
} from "../services/api";

export function useStreams() {
  return useQuery({
    queryKey: ["streams"],
    queryFn: getStreams,
  });
}

export function useStream(id: string) {
  return useQuery({
    queryKey: ["streams", id],
    queryFn: () => getStream(id),
    enabled: !!id,
  });
}

export function useCreateStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createStream,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
    },
  });
}

export function useUpdateStream(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof updateStream>[1]) => updateStream(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["streams", id] });
    },
  });
}

export function useDeleteStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteStream,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
    },
  });
}

export function useAddToStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, streamId, position }: { workId: string; streamId: string; position?: number }) =>
      addToStream(workId, streamId, position),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });
}

export function useRemoveFromStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, streamId }: { workId: string; streamId: string }) =>
      removeFromStream(workId, streamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });
}
