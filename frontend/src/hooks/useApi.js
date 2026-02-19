import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/axios";
export { useResultsByCategory } from "./useResultsByCategory";

// GET /competitions/:id/detail
export function useCompetitionDetail(id) {
  return useQuery({
    queryKey: ["competition", id, "detail"],
    queryFn: async () => {
      const { data } = await api.get(`/v1/competitions/${id}/detail`);
      return data;
    },
    enabled: !!id,
  });
}

// GET /auth/me
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data } = await api.get("/v1/auth/me");
      return data;
    },
  });
}

export function usePairAthlete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (athlete_id) => {
      const { data } = await api.patch("/v1/me/pair-athlete", { athlete_id });
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
        `/v1/athletes/search?q=${encodeURIComponent(query)}`,
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
      const { data } = await api.get(`/v1/athletes/${athleteId}/overview`);
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
      const { data } = await api.get("/v1/athletes");
      return data;
    },
  });
}

// GET /athletes/:id/detail
export function useAthleteDetail(id) {
  return useQuery({
    queryKey: ["athlete", id, "detail"],
    queryFn: async () => {
      const { data } = await api.get(`/v1/athletes/${id}/detail`);
      return data;
    },
    enabled: !!id,
  });
}

// GET /competitions
export function useCompetitions() {
  return useQuery({
    queryKey: ["competitions"],
    queryFn: async () => {
      const { data } = await api.get("/v1/competitions");
      return data;
    },
  });
}

// GET /athletes/:id/performance-by-year
export function useAthletePerformanceByYear(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "performance-by-year"],
    queryFn: async () => {
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/performance-by-year`,
      );
      return data;
    },
    enabled: !!athleteId,
  });
}

// GET /athletes/:id/anomalies
export function useAthleteAnomalies(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "anomalies"],
    queryFn: async () => {
      const { data } = await api.get(`/v1/athletes/${athleteId}/anomalies`);
      return data;
    },
    enabled: !!athleteId,
  });
}
