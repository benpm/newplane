/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
// plane imports
import { Button } from "@plane/propel/button";
import { FolderGit2 } from "lucide-react";
import { Spinner } from "@plane/ui";
import { truncateText } from "@plane/utils";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserProfile, useUserSettings } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
// services
import { ProjectService } from "@/services/project";
import { UserService } from "@/services/user.service";
// local components
import { CommonOnboardingHeader } from "../common";

type Props = {
  handleNextStep: () => Promise<void>;
  handleCurrentViewChange?: () => void;
  hasInvitations?: boolean;
};

const projectService = new ProjectService();
const userService = new UserService();

export function WorkspaceJoinProjectsStep(props: Props) {
  const { handleNextStep, handleCurrentViewChange, hasInvitations = false } = props;
  const router = useAppRouter();

  // states
  const [isJoining, setIsJoining] = useState<string | null>(null);

  // store hooks
  const { fetchWorkspaces } = useWorkspace();
  const { fetchCurrentUserSettings } = useUserSettings();
  const { updateUserProfile } = useUserProfile();

  const { data: adminStatus } = useSWR("INSTANCE_ADMIN_STATUS", () => userService.currentUserInstanceAdminStatus());
  const isInstanceAdmin = adminStatus?.is_instance_admin ?? false;

  const { data: projects, isLoading } = useSWR("USER_JOINABLE_PROJECTS", () => projectService.getJoinableProjects());

  const handleJoinProject = async (projectId: string) => {
    setIsJoining(projectId);
    try {
      const res = await projectService.joinProject(projectId);
      await fetchWorkspaces();
      await fetchCurrentUserSettings();
      await updateUserProfile({
        last_workspace_id: res.workspace_slug,
      });
      await handleNextStep();
      router.push(`/${res.workspace_slug}/projects/${res.project_id}/issues`);
    } catch (error) {
      console.error(error);
      setIsJoining(null);
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <CommonOnboardingHeader
        title="Join an existing project"
        description="Select an active project below to get started."
      />

      <div className="flex flex-col gap-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner className="size-6" />
          </div>
        ) : projects && projects.length > 0 ? (
          projects.map((project) => (
            <div
              key={project.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-subtle p-3 hover:bg-surface-2 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-layer-2 border border-subtle text-16 font-medium">
                  {project.emoji ? project.emoji : <FolderGit2 className="size-4 text-tertiary" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-13 font-medium text-primary truncate">
                      {truncateText(project.name, 35)}
                    </span>
                    <span className="text-11 font-mono text-tertiary bg-layer-2 px-1.5 py-0.5 rounded">
                      {project.identifier}
                    </span>
                  </div>
                  <p className="text-11 text-secondary truncate">
                    Workspace: <span className="font-medium text-primary">{project.workspace.name}</span>
                  </p>
                </div>
              </div>

              <div className="shrink-0">
                <Button
                  variant="primary"
                  size="sm"
                  loading={isJoining === project.id}
                  disabled={Boolean(isJoining)}
                  onClick={() => handleJoinProject(project.id)}
                >
                  Join Project
                </Button>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-8 flex flex-col items-center gap-2">
            <span className="text-14 font-medium text-primary">No joinable projects available</span>
            <span className="text-13 text-tertiary max-w-sm">
              There are no public projects to join right now. Please ask an administrator to add you to a project or send you an invitation.
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-subtle">
        {hasInvitations && handleCurrentViewChange ? (
          <Button variant="link" size="sm" onClick={handleCurrentViewChange}>
            View Workspace Invitations
          </Button>
        ) : <div />}

        {isInstanceAdmin && handleCurrentViewChange ? (
          <Button variant="link" size="sm" onClick={handleCurrentViewChange} className="text-tertiary hover:text-primary">
            Admin: Create Workspace
          </Button>
        ) : null}
      </div>
    </div>
  );
}
