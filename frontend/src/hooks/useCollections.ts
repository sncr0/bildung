import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getCollections,
  getCollection,
  createCollection,
  updateCollection,
  deleteCollection,
  addToCollection,
  removeFromCollection,
  addCollectionToStream,
  removeCollectionFromStream,
  type CollectionType,
} from "../services/api";

export function useCollections(params?: { author_id?: string; type?: CollectionType }) {
  return useQuery({
    queryKey: ["collections", params],
    queryFn: () => getCollections(params),
  });
}

export function useCollection(id: string) {
  return useQuery({
    queryKey: ["collections", id],
    queryFn: () => getCollection(id),
    enabled: !!id,
  });
}

export function useCreateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
    },
  });
}

export function useUpdateCollection(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof updateCollection>[1]) => updateCollection(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["collections", id] });
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
    },
  });
}

export function useDeleteCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
    },
  });
}

export function useAddToCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, collectionId, order }: { workId: string; collectionId: string; order?: number }) =>
      addToCollection(workId, collectionId, order),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });
}

export function useRemoveFromCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, collectionId }: { workId: string; collectionId: string }) =>
      removeFromCollection(workId, collectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });
}

export function useAddCollectionToStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, streamId, order }: { collectionId: string; streamId: string; order?: number }) =>
      addCollectionToStream(collectionId, streamId, order),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}

export function useRemoveCollectionFromStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, streamId }: { collectionId: string; streamId: string }) =>
      removeCollectionFromStream(collectionId, streamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}
