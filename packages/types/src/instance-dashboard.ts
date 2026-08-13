/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TServiceStatus = "ok" | "degraded" | "down" | "unknown";

export type TServiceProbe<D = Record<string, unknown>> = {
  status: TServiceStatus;
  latency_ms: number | null;
  error: string | null;
  details: D;
};

export type TWorkerDetail = {
  name: string;
  active_tasks: number;
  uptime: string | null;
  pool_info: string | null;
};

export type TStaleTask = {
  name: string;
  last_run_at: string | null;
  expected_interval_seconds: number | null;
  seconds_since_last_run: number | null;
};

export type TInstanceHealth = {
  checked_at: string;
  overall: TServiceStatus;
  services: {
    postgres: TServiceProbe<{
      server_version?: string;
      database?: string;
      active_connections?: number;
      max_connections?: number;
      database_size_bytes?: number;
    }>;
    redis: TServiceProbe<{
      server?: string;
      version?: string;
      uptime_seconds?: number;
      used_memory_bytes?: number;
      maxmemory_bytes?: number;
      connected_clients?: number;
      evicted_keys?: number;
      keyspace_hits?: number;
      keyspace_misses?: number;
      keys?: number;
    }>;
    rabbitmq: TServiceProbe<{
      host?: string;
      port?: string | number;
      vhost?: string;
      queues?: { name: string; messages: number | null; consumers: number | null; note?: string }[];
    }>;
    object_storage: TServiceProbe<{ backend?: string; bucket?: string; endpoint?: string }>;
    celery_workers: TServiceProbe<{
      workers?: TWorkerDetail[];
      total_workers?: number;
      total_active_tasks?: number;
    }>;
    celery_beat: TServiceProbe<{
      enabled_task_count?: number;
      last_run_at?: string | null;
      seconds_since_last_run?: number | null;
      stale_tasks?: TStaleTask[];
    }>;
  };
  runtime: {
    instance_id: string | null;
    instance_name: string | null;
    current_version: string | null;
    latest_version: string | null;
    edition: string | null;
    is_setup_done: boolean;
    debug: boolean;
    python_version: string;
    django_version: string;
    smtp: {
      configured: boolean;
      host?: string | null;
      port?: string | null;
      from_address?: string | null;
      use_tls?: boolean;
      use_ssl?: boolean;
    };
  };
};

export type TInstanceOverview = {
  workspaces: number;
  users: {
    total: number;
    active: number;
    bots: number;
    instance_admins: number;
    joined_last_30d: number;
    active_last_7d: number;
  };
  projects: { total: number; archived: number; global: number };
  work_items: {
    total: number;
    by_state_group: Record<string, number>;
    created_last_7d: number;
    created_last_30d: number;
  };
  cycles: number;
  modules: number;
  pages: number;
  comments: number;
  views: number;
  labels: number;
  attachments: number;
  departments: number;
  staff: number;
};

export type TBucketScan = {
  /** `never` until a scan is run; `stale` once the cached result ages out. */
  status: "never" | "fresh" | "stale" | "running" | "error";
  bucket?: string;
  object_count?: number;
  total_bytes?: number;
  truncated?: boolean;
  duration_ms?: number;
  scanned_at?: string;
  error?: string;
};

export type TInstanceStorage = {
  postgres: {
    database_size_bytes: number;
    largest_tables: {
      table: string;
      total_bytes: number;
      table_bytes: number;
      index_bytes: number;
      /** Estimate left by the last ANALYZE, not an exact count. */
      row_estimate: number;
    }[];
  };
  assets: {
    /** Client-declared sizes: a reservation, not a measurement. */
    declared_bytes: number;
    /** Real ContentLength readings, where the upload recorded one. */
    measured_bytes: number;
    /** Share of uploaded assets that carry a real measurement. */
    measured_coverage: number | null;
    uploaded_count: number;
    measured_count: number;
    pending_bytes: number;
    pending_count: number;
    soft_deleted_bytes: number;
    soft_deleted_count: number;
    by_entity_type: { entity_type: string; count: number; best_effort_bytes: number }[];
    by_workspace: {
      workspace_id: string;
      workspace_slug: string;
      workspace_name: string;
      count: number;
      best_effort_bytes: number;
    }[];
  };
  bucket_scan: TBucketScan;
};

export type TScheduledJob = {
  id: number;
  name: string;
  task: string;
  schedule_display: string;
  enabled: boolean;
  last_run_at: string | null;
  total_run_count: number;
  expected_interval_seconds: number | null;
  seconds_since_last_run: number | null;
  is_stale: boolean;
};

export type TDashboardWorkspace = {
  id: string;
  name: string;
  slug: string;
  owner: string | null;
  logo_url: string | null;
  total_projects: number;
  total_members: number;
  total_issues: number;
  created_at: string;
};

export type TDashboardUser = {
  id: string;
  email: string;
  display_name: string;
  first_name: string;
  last_name: string;
  avatar_url: string | null;
  is_active: boolean;
  is_bot: boolean;
  is_instance_admin: boolean;
  workspace_count: number;
  date_joined: string;
  last_login: string | null;
};

export type TDashboardProject = {
  id: string;
  name: string;
  identifier: string;
  workspace_id: string;
  workspace_slug: string;
  workspace_name: string;
  lead: string | null;
  network: number;
  is_global: boolean;
  is_archived: boolean;
  member_count: number;
  issue_count: number;
  created_at: string;
};

export type TDashboardInvite = {
  id: string;
  email: string;
  /** Name to apply to the account on acceptance; blank for stock invites. */
  display_name: string;
  role: number;
  workspace_id: string;
  workspace_slug: string;
  workspace_name: string;
  accepted: boolean;
  responded_at: string | null;
  created_at: string;
  /** The URL to hand to the invitee — same shape the email flow sends. */
  link: string;
  /** True when an outstanding invite was updated instead of a new one made. */
  reused?: boolean;
};

export type TDashboardInvitePayload = {
  email: string;
  display_name?: string;
  workspace_id: string;
  role: number;
};

/** Cursor-paginated envelope returned by `BasePaginator.paginate`. */
export type TDashboardPaginated<T> = {
  results: T[];
  next_cursor?: string;
  prev_cursor?: string;
  next_page_results?: boolean;
  prev_page_results?: boolean;
  count?: number;
  total_count?: number;
  total_pages?: number;
};
