/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useEffect, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import type { IWorkspaceMemberInvitation } from "@plane/types";
import { ECreateOrJoinWorkspaceViews, EOnboardingSteps } from "@plane/types";
// hooks
import { useUser } from "@/hooks/store/user";
import { UserService } from "@/services/user.service";
// local components
import { WorkspaceCreateStep, WorkspaceJoinInvitesStep, WorkspaceJoinProjectsStep } from "./";

type Props = {
  invitations: IWorkspaceMemberInvitation[];
  handleStepChange: (step: EOnboardingSteps, skipInvites?: boolean) => void;
};

const userService = new UserService();

enum EWorkspaceExtendedViews {
  WORKSPACE_JOIN_PROJECTS = "WORKSPACE_JOIN_PROJECTS",
}

export const WorkspaceSetupStep = observer(function WorkspaceSetupStep({ invitations, handleStepChange }: Props) {
  // states
  const [currentView, setCurrentView] = useState<ECreateOrJoinWorkspaceViews | EWorkspaceExtendedViews | null>(null);
  // store hooks
  const { data: user } = useUser();
  const { data: adminStatus } = useSWR("INSTANCE_ADMIN_STATUS", () => userService.currentUserInstanceAdminStatus());
  const isInstanceAdmin = adminStatus?.is_instance_admin ?? false;

  useEffect(() => {
    if (invitations.length > 0) {
      setCurrentView(ECreateOrJoinWorkspaceViews.WORKSPACE_JOIN);
    } else {
      // Show existing projects to join instead of create workspace
      setCurrentView(EWorkspaceExtendedViews.WORKSPACE_JOIN_PROJECTS);
    }
  }, [invitations]);

  return (
    <>
      {currentView === ECreateOrJoinWorkspaceViews.WORKSPACE_JOIN ? (
        <WorkspaceJoinInvitesStep
          invitations={invitations}
          handleNextStep={async () => {
            handleStepChange(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN, true);
          }}
          handleCurrentViewChange={() =>
            setCurrentView(
              isInstanceAdmin
                ? ECreateOrJoinWorkspaceViews.WORKSPACE_CREATE
                : EWorkspaceExtendedViews.WORKSPACE_JOIN_PROJECTS
            )
          }
        />
      ) : currentView === EWorkspaceExtendedViews.WORKSPACE_JOIN_PROJECTS ? (
        <WorkspaceJoinProjectsStep
          handleNextStep={async () => {
            handleStepChange(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN, true);
          }}
          handleCurrentViewChange={() => {
            if (invitations.length > 0) {
              setCurrentView(ECreateOrJoinWorkspaceViews.WORKSPACE_JOIN);
            } else if (isInstanceAdmin) {
              setCurrentView(ECreateOrJoinWorkspaceViews.WORKSPACE_CREATE);
            }
          }}
          hasInvitations={invitations.length > 0}
        />
      ) : (
        <WorkspaceCreateStep
          user={user}
          onComplete={(skipInvites) => handleStepChange(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN, skipInvites)}
          handleCurrentViewChange={() => setCurrentView(EWorkspaceExtendedViews.WORKSPACE_JOIN_PROJECTS)}
          hasInvitations={invitations.length > 0}
        />
      )}
    </>
  );
});
