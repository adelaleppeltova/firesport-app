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
      const { data } = await api.get("/v1/me/");
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

// GET /athletes (paginated + search)
export function useAthletes({ search = "", page = 1, pageSize = 25 } = {}) {
  return useQuery({
    queryKey: ["athletes", "list", search, page, pageSize],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set("q", search);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const { data } = await api.get(`/v1/athletes?${params.toString()}`);
      return data;
    },
    keepPreviousData: true,
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

// GET /competitions (paginated + search + sort)
export function useCompetitions({
  search = "",
  page = 1,
  pageSize = 25,
  sortKey = "date",
  sortDir = "desc",
} = {}) {
  return useQuery({
    queryKey: [
      "competitions",
      "list",
      search,
      page,
      pageSize,
      sortKey,
      sortDir,
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set("q", search);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      params.set("sort_key", sortKey);
      params.set("sort_dir", sortDir);
      const { data } = await api.get(`/v1/competitions?${params.toString()}`);
      return data;
    },
    keepPreviousData: true,
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

// GET /athletes/:id/performance-in-year
export function useAthletePerformanceInYear(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "performance-in-year"],
    queryFn: async () => {
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/performance-in-year`,
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
