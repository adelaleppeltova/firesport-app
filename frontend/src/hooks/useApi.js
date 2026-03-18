import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
  useQueries,
} from "@tanstack/react-query";
import { useMemo } from "react";
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
      const { data } = await api.get("/v1/me");
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

export function useUnpairAthlete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.delete("/v1/me/pair-athlete");
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
    placeholderData: keepPreviousData,
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

// GET /athletes/:id/profile – základní profil pro MyProfile
export function useAthleteProfile(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "profile"],
    queryFn: async () => {
      const { data } = await api.get(`/v1/athletes/${athleteId}/profile`);
      return data;
    },
    enabled: !!athleteId,
  });
}

// GET /athletes/:id/performance-history – trend výkonnosti pro History
export function useAthletePerformanceHistory(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "performance-history"],
    queryFn: async () => {
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/performance-history`,
      );
      return data;
    },
    enabled: !!athleteId,
  });
}

// GET /athletes/:id/performance-stability – stabilita výkonu pro PerformanceStability
export function useAthletePerformanceStability(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "performance-stability"],
    queryFn: async () => {
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/performance-stability`,
      );
      return data;
    },
    enabled: !!athleteId,
  });
}

// GET /athletes (paginated + search)
export function useAthletes({
  search = "",
  page = 1,
  pageSize = 25,
  anomalyStatus,
  runId,
} = {}) {
  return useQuery({
    queryKey: [
      "athletes",
      "list",
      search,
      page,
      pageSize,
      anomalyStatus,
      runId,
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set("q", search);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (anomalyStatus) params.set("anomaly_status", anomalyStatus);
      if (runId) params.set("run_id", runId);
      const { data } = await api.get(`/v1/athletes?${params.toString()}`);
      return data;
    },
    placeholderData: keepPreviousData,
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
    placeholderData: keepPreviousData,
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
export function useAthleteAnomalies(athleteId, runId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "anomalies", runId ?? null],
    queryFn: async () => {
      const params = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/anomalies${params}`,
      );
      return data;
    },
    enabled: !!athleteId && !!runId,
  });
}

// Fetch items from ALL windows for an athlete, deduplicated by result_id.
// Returns { items, runIdsByCategory } where runIdsByCategory is a
// Map<category_group, Set<run_id>> used to filter windows by category.
export function useAllAthleteAnomalyItems(athleteId, windows) {
  const windowList = windows ?? [];

  const queries = useQueries({
    queries: windowList.map((w) => ({
      queryKey: ["athletes", athleteId, "anomalies", w.run_id],
      queryFn: async () => {
        const { data } = await api.get(
          `/v1/athletes/${athleteId}/anomalies?run_id=${encodeURIComponent(w.run_id)}`,
        );
        return data;
      },
      enabled: !!athleteId && !!w.run_id,
      staleTime: 5 * 60 * 1000,
    })),
  });

  return useMemo(() => {
    const seen = new Set();
    const combined = [];
    // Map<category_group, Set<run_id>>
    const runIdsByCategory = new Map();

    for (let i = 0; i < queries.length; i++) {
      const runId = windowList[i]?.run_id;
      for (const item of queries[i].data?.items ?? []) {
        // Build category → run_id mapping (before dedup so all windows counted)
        if (item.category_group && runId) {
          if (!runIdsByCategory.has(item.category_group)) {
            runIdsByCategory.set(item.category_group, new Set());
          }
          runIdsByCategory.get(item.category_group).add(runId);
        }
        // Deduplicate items by result_id
        if (!seen.has(item.result_id)) {
          seen.add(item.result_id);
          combined.push(item);
        }
      }
    }
    return { items: combined, runIdsByCategory };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queries]);
}

// GET /ml/windows?type=yearly_3y[&athlete_id=...]
export function useMlWindows(type = "yearly_3y", athleteId = null) {
  return useQuery({
    queryKey: ["ml", "windows", type, athleteId ?? null],
    queryFn: async () => {
      const params = new URLSearchParams({ type });
      if (athleteId) params.set("athlete_id", athleteId);
      const { data } = await api.get(`/v1/ml/windows?${params.toString()}`);
      return data; // list of WindowListItem
    },
    enabled: !!athleteId, // načteme teprve po výběru závodníka
    staleTime: 2 * 60 * 1000,
  });
}

// GET /athletes/:id/category-stats
export function useAthleteCategoryStats(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "category-stats"],
    queryFn: async () => {
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/category-stats`,
      );
      return data; // { stats: { [category_group]: { total_races, best_time } } }
    },
    enabled: !!athleteId,
    staleTime: 5 * 60 * 1000,
  });
}

// GET /athletes/:id/per-category-stats
export function useAthletePerCategoryStats(athleteId) {
  return useQuery({
    queryKey: ["athletes", athleteId, "per-category-stats"],
    queryFn: async () => {
      const { data } = await api.get(
        `/v1/athletes/${athleteId}/per-category-stats`,
      );
      return data; // { categories: [{ category_id, category_name, total_races, best_time }] }
    },
    enabled: !!athleteId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAdminImportReview() {
  return useQuery({
    queryKey: ["admin", "import-review"],
    queryFn: async () => {
      const { data } = await api.get("/v1/admin/import/review");
      return data;
    },
  });
}

export function useAdminImportResults() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files) => {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append("files", file);
      });
      const { data } = await api.post("/v1/admin/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "import-review"] });
    },
  });
}

export function useAdminAssignResultAthlete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ resultId, athleteId }) => {
      const { data } = await api.post(
        `/v1/admin/results/${resultId}/assign-athlete`,
        { athlete_id: athleteId },
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "import-review"] });
    },
  });
}

export function useAdminCreateAthleteFromResult() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (resultId) => {
      const { data } = await api.post(`/v1/admin/results/${resultId}/create-athlete`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "import-review"] });
    },
  });
}

export function useAdminUnassignResultAthlete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (resultId) => {
      const { data } = await api.post(
        `/v1/admin/results/${resultId}/unassign-athlete`,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "import-review"] });
    },
  });
}

export function useAdminDeleteReviewResults() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.delete("/v1/admin/import/review");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "import-review"] });
    },
  });
}

export function useAdminAthleteSearch(query) {
  return useQuery({
    queryKey: ["admin", "athletes", "search", query],
    queryFn: async () => {
      if (!query || query.trim().length < 2) {
        return { items: [] };
      }
      const { data } = await api.get(
        `/v1/admin/athletes/search?q=${encodeURIComponent(query.trim())}`,
      );
      return data;
    },
    enabled: query.trim().length >= 2,
    placeholderData: keepPreviousData,
  });
}

export function useAdminAthleteMergeCandidates(athleteId, query) {
  return useQuery({
    queryKey: ["admin", "athletes", athleteId, "merge-candidates", query],
    queryFn: async () => {
      if (!athleteId) {
        return { items: [] };
      }
      const params = new URLSearchParams({ athlete_id: athleteId });
      if (query?.trim()) {
        params.set("q", query.trim());
      }
      const { data } = await api.get(
        `/v1/admin/athletes/merge-candidates?${params.toString()}`,
      );
      return data;
    },
    enabled: !!athleteId,
    placeholderData: keepPreviousData,
  });
}

export function useAdminMergeAthletes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ sourceAthleteId, targetAthleteId }) => {
      const { data } = await api.post(
        `/v1/admin/athletes/${sourceAthleteId}/merge-into/${targetAthleteId}`,
      );
      return data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["athlete", variables.sourceAthleteId, "detail"],
      });
      queryClient.invalidateQueries({
        queryKey: ["athlete", variables.targetAthleteId, "detail"],
      });
      queryClient.invalidateQueries({ queryKey: ["athletes"] });
      queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });
}
