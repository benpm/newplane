/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TProjectGithubSync = {
  id: string;
  project: string;
  workspace: string;
  repository: string;
  repository_owner: string;
  repository_name: string;
  is_issue_sync_enabled: boolean;
  is_wiki_sync_enabled: boolean;
  last_sync_status: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
};

export class CEProjectGithubSyncService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetch(workspaceSlug: string, projectId: string): Promise<TProjectGithubSync | null> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-sync/`)
      .then((response) => response?.data ?? null)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async connect(
    workspaceSlug: string,
    projectId: string,
    data: { repository: string; is_issue_sync_enabled?: boolean; is_wiki_sync_enabled?: boolean }
  ): Promise<TProjectGithubSync> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-sync/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    projectId: string,
    data: Partial<Pick<TProjectGithubSync, "is_issue_sync_enabled" | "is_wiki_sync_enabled"> & { repository: string }>
  ): Promise<TProjectGithubSync> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-sync/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async disconnect(workspaceSlug: string, projectId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-sync/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async syncNow(workspaceSlug: string, projectId: string): Promise<void> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/github-sync/sync-now/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
