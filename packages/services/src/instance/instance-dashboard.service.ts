/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TBucketScan,
  TDashboardPaginated,
  TDashboardProject,
  TDashboardUser,
  TDashboardWorkspace,
  TInstanceHealth,
  TInstanceOverview,
  TInstanceStorage,
  TScheduledJob,
} from "@plane/types";
import { APIService } from "../api.service";

/**
 * Instance dashboard API.
 *
 * Note the base path: `instance-dashboard`, not `instances/...`. The session
 * middleware reads the god-mode cookie for any path containing "instances",
 * and these endpoints are called from the web app, which holds the app
 * session cookie. Renaming the path would silently 403 every request.
 */
export class InstanceDashboardService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchHealth(): Promise<TInstanceHealth> {
    return this.get("/api/instance-dashboard/health/")
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchOverview(): Promise<TInstanceOverview> {
    return this.get("/api/instance-dashboard/overview/")
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchStorage(): Promise<TInstanceStorage> {
    return this.get("/api/instance-dashboard/storage/")
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Walk the object store. Bounded server-side, but still seconds, not ms. */
  async runBucketScan(): Promise<TBucketScan> {
    return this.post("/api/instance-dashboard/storage/bucket-scan/", {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchScheduledJobs(): Promise<{ results: TScheduledJob[] }> {
    return this.get("/api/instance-dashboard/scheduled-jobs/")
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchWorkspaces(params?: Record<string, string>): Promise<TDashboardPaginated<TDashboardWorkspace>> {
    return this.get("/api/instance-dashboard/workspaces/", { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchUsers(params?: Record<string, string>): Promise<TDashboardPaginated<TDashboardUser>> {
    return this.get("/api/instance-dashboard/users/", { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchProjects(params?: Record<string, string>): Promise<TDashboardPaginated<TDashboardProject>> {
    return this.get("/api/instance-dashboard/projects/", { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
