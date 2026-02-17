import { useQuery } from "@tanstack/react-query";
import api from "../api/axios";

// Fetch results for a given competition and category
export function useResultsByCategory(competitionId, categoryId) {
  return useQuery({
    queryKey: ["results", competitionId, categoryId],
    queryFn: async () => {
      if (!competitionId || !categoryId) return [];
      const { data } = await api.get(
        `/v1/competitions/${competitionId}/results/${categoryId}`,
      );
      return data;
    },
    enabled: !!competitionId && !!categoryId,
  });
}
