/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useProject } from "@/hooks/store/use-project";

/**
 * Returns the id of the workspace's only project, or undefined when there are zero or several.
 * Joined projects are counted first; accessible workspace projects are the fallback when none are joined.
 * Both store getters are scoped to the current workspace, so this follows workspace switches.
 * Must be called from an observer component.
 */
export const useSingleProjectId = (): string | undefined => {
  const { joinedProjectIds, workspaceProjectIds } = useProject();
  const projectIds = joinedProjectIds.length > 0 ? joinedProjectIds : (workspaceProjectIds ?? []);
  return projectIds.length === 1 ? projectIds[0] : undefined;
};
