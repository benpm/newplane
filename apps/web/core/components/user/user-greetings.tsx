/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane types
import type { IUser } from "@plane/types";
// hooks
import { useProject } from "@/hooks/store/use-project";
// services
import { UserService } from "@/services/user.service";

const userService = new UserService();

export interface IUserGreetingsView {
  user: IUser;
}

export const UserGreetingsView = observer(function UserGreetingsView(props: IUserGreetingsView) {
  const { user } = props;
  const { workspaceSlug } = useParams();
  const { joinedProjectIds, getProjectById, getPartialProjectById, loader } = useProject();

  const isProjectsLoading = loader === "init-loader";

  // First public project associated with user (joined)
  const joinedPublicProjects = (joinedProjectIds || [])
    .map((id) => getProjectById(id) || getPartialProjectById(id))
    .filter((p) => Boolean(p && p.network === 2 && !p.archived_at));

  const defaultProject = joinedPublicProjects[0];

  const { data: userStats, isLoading: isStatsLoading } = useSWR(
    workspaceSlug && user?.id ? `USER_STATS_${workspaceSlug}_${user.id}` : null,
    () => userService.getUserProfileData(workspaceSlug.toString(), user.id),
    { revalidateIfStale: false, revalidateOnFocus: true }
  );

  const { data: segregationData } = useSWR(
    workspaceSlug && user?.id ? `USER_PROJECT_SEGREGATION_${workspaceSlug}_${user.id}` : null,
    () => userService.getUserProfileProjectsSegregation(workspaceSlug.toString(), user.id),
    { revalidateIfStale: false, revalidateOnFocus: true }
  );

  const projectStats = defaultProject
    ? segregationData?.project_data?.find((p) => p.id === defaultProject.id)
    : undefined;

  const assignedCount =
    projectStats !== undefined ? projectStats.assigned_issues : segregationData ? 0 : (userStats?.assigned_issues ?? 0);

  return (
    <div className="flex flex-col items-center justify-center my-6 select-none">
      <div className="text-9xl sm:text-[10rem] md:text-[12rem] leading-none mb-3 transition-transform duration-200 hover:scale-105">
        🐭
      </div>
      {isProjectsLoading ? (
        <span className="text-sm font-medium text-placeholder animate-pulse">Loading...</span>
      ) : !defaultProject ? (
        <span className="text-sm font-medium text-placeholder">no projects :(</span>
      ) : (
        <Link
          href={`/${workspaceSlug}/projects/${defaultProject.id}/issues/?layout=kanban&user_filter=true`}
          className="text-sm font-medium text-secondary hover:text-primary transition-colors underline-offset-4 hover:underline cursor-pointer"
        >
          {isStatsLoading && !userStats && !segregationData
            ? "..."
            : `${assignedCount} assigned ${assignedCount === 1 ? "task" : "tasks"}`}
        </Link>
      )}
    </div>
  );
});
