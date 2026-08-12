/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TServiceStatus } from "@plane/types";

/** Prefix every SWR key so the header refresh button can match on it. */
export const SWR_KEY = {
  HEALTH: "INSTANCE_DASHBOARD_HEALTH",
  OVERVIEW: "INSTANCE_DASHBOARD_OVERVIEW",
  STORAGE: "INSTANCE_DASHBOARD_STORAGE",
  JOBS: "INSTANCE_DASHBOARD_JOBS",
  WORKSPACES: "INSTANCE_DASHBOARD_WORKSPACES",
  USERS: "INSTANCE_DASHBOARD_USERS",
  PROJECTS: "INSTANCE_DASHBOARD_PROJECTS",
} as const;

export const SWR_KEY_PREFIX = "INSTANCE_DASHBOARD_";

/**
 * Health refreshes on a timer because it is the only panel whose value
 * changes on its own; the server caches it for 15s, so this costs little.
 * Everything else is refreshed by hand.
 */
export const HEALTH_REFRESH_INTERVAL_MS = 30_000;

export const SEARCH_DEBOUNCE_MS = 300;

export const DASHBOARD_TABS = ["health", "overview", "storage", "inventory"] as const;
export type TDashboardTab = (typeof DASHBOARD_TABS)[number];

/** Propel Badge variant per service status. */
export const STATUS_VARIANT: Record<TServiceStatus, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  degraded: "warning",
  down: "danger",
  unknown: "neutral",
};

/**
 * Recharts needs literal colours, so these cannot be semantic Tailwind
 * tokens. Kept in one place, as the god-mode usage monitor does.
 */
export const CHART_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316"];

/** Stable colours for the work-item state groups, matching Plane's palette. */
export const STATE_GROUP_COLORS: Record<string, string> = {
  backlog: "#8B8D98",
  unstarted: "#3B82F6",
  started: "#F59E0B",
  completed: "#10B981",
  cancelled: "#EF4444",
  triage: "#8B5CF6",
  none: "#D1D5DB",
};
