import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/axios";

// GET /auth/me
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data } = await api.get("/auth/me");
      return data;
    },
  });
}

export function usePairAthlete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (athlete_id) => {
      const { data } = await api.patch("/user/me/athlete", { athlete_id });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(["me"]);
    },
  });
}

export function useSearchAthletes(query) {
  return useQuery({
    queryKey: ["athletes", "search", query],
    queryFn: async () => {
      if (!query || query.length < 2) return { items: [] };
      const { data } = await api.get(
        `/athletes/search?q=${encodeURIComponent(query)}`
      );
      return data;
    },
    enabled: query.length >= 2,
  });
}

export function useAthleteOverview(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "overview"],
    queryFn: async () => {
      const { data } = await api.get(`/athletes/${athleteId}/overview`);
      return data;
    },
    enabled: !!athleteId,
  });
}

// GET /athletes
export function useAthletes() {
  return useQuery({
    queryKey: ["athletes", "all"],
    queryFn: async () => {
      const { data } = await api.get("/athletes");
      return data;
    },
  });
}
