/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isEmpty } from "lodash-es";
import { observer } from "mobx-react";
// plane helpers
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
// components
import { SidebarWrapper } from "@/components/sidebar/sidebar-wrapper";
import { SidebarFavoritesMenu } from "@/components/workspace/sidebar/favorites/favorites-menu";
import { SidebarProjectsList } from "@/components/workspace/sidebar/projects-list";
import { SidebarQuickActions } from "@/components/workspace/sidebar/quick-actions";
import { SidebarMenuItems } from "@/components/workspace/sidebar/sidebar-menu-items";
// hooks
import { useFavorite } from "@/hooks/store/use-favorite";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// plane web components
import { SidebarTeamsList } from "@/plane-web/components/workspace/sidebar/teams-sidebar-list";

export const AppSidebar = observer(function AppSidebar() {
  // store hooks
  const { allowPermissions } = useUserPermissions();
  const { groupedFavorites } = useFavorite();
  const { joinedProjectIds, workspaceProjectIds } = useProject();

  // derived values
  const canPerformWorkspaceMemberActions = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );

  const isFavoriteEmpty = isEmpty(groupedFavorites);

  const projectsList = joinedProjectIds && joinedProjectIds.length > 0 ? joinedProjectIds : (workspaceProjectIds ?? []);
  const isSingleProject = projectsList.length === 1;
  const singleProjectId = isSingleProject ? projectsList[0] : undefined;

  return (
    <SidebarWrapper title="Projects" quickActions={<SidebarQuickActions />}>
      <SidebarMenuItems singleProjectId={singleProjectId} />
      {/* Favorites Menu */}
      {canPerformWorkspaceMemberActions && !isFavoriteEmpty && <SidebarFavoritesMenu />}
      {/* Teams List */}
      {!isSingleProject && <SidebarTeamsList />}
      {/* Projects List */}
      {!isSingleProject && <SidebarProjectsList />}
    </SidebarWrapper>
  );
});
