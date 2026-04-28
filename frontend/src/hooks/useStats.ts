import { useQuery } from "@tanstack/react-query";
import { getStats } from "../services/api";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });
}
