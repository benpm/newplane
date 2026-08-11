/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { IGlobalProject } from "@plane/types";
import { APIService } from "@/services/api.service";

export class GlobalProjectsService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchAll(workspaceSlug: string, showArchived?: boolean): Promise<IGlobalProject[]> {
    const query = showArchived ? "?show_archived=true" : "";
    return this.get(`/api/workspaces/${workspaceSlug}/global-projects/${query}`)
      .then(({ data }: { data: IGlobalProject[] }) => data)
      .catch((error: { response?: { data: unknown } }) => {
        throw error?.response?.data;
      });
  }
}
