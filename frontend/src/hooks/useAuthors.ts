import { useQuery } from "@tanstack/react-query";
import { getAuthors, getAuthor } from "../services/api";

export function useAuthors() {
  return useQuery({
    queryKey: ["authors"],
    queryFn: getAuthors,
  });
}

export function useAuthor(id: string) {
  return useQuery({
    queryKey: ["authors", id],
    queryFn: () => getAuthor(id),
    enabled: !!id,
  });
}
