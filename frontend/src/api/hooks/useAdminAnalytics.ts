import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type {
  AnalyticsRange,
  AnalyticsSummary,
  SlowEndpointRow,
  TopSearchRow,
  UserStatsRow,
} from "../../types";

export function useAnalyticsSummary(range: AnalyticsRange) {
  return useQuery<AnalyticsSummary>({
    queryKey: ["admin-analytics", "summary", range],
    queryFn: () =>
      client
        .get<AnalyticsSummary>(`/admin/analytics/summary`, { params: { range } })
        .then((r) => r.data),
  });
}

export function useAnalyticsUsers(range: AnalyticsRange) {
  return useQuery<UserStatsRow[]>({
    queryKey: ["admin-analytics", "users", range],
    queryFn: () =>
      client
        .get<UserStatsRow[]>(`/admin/analytics/users`, { params: { range } })
        .then((r) => r.data),
  });
}

export function useAnalyticsTopSearches(range: AnalyticsRange, limit = 20) {
  return useQuery<TopSearchRow[]>({
    queryKey: ["admin-analytics", "top-searches", range, limit],
    queryFn: () =>
      client
        .get<TopSearchRow[]>(`/admin/analytics/top-searches`, {
          params: { range, limit },
        })
        .then((r) => r.data),
  });
}

export function useAnalyticsSlowEndpoints(range: AnalyticsRange, limit = 20) {
  return useQuery<SlowEndpointRow[]>({
    queryKey: ["admin-analytics", "slow-endpoints", range, limit],
    queryFn: () =>
      client
        .get<SlowEndpointRow[]>(`/admin/analytics/slow-endpoints`, {
          params: { range, limit },
        })
        .then((r) => r.data),
  });
}
