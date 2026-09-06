/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
// plane types
import { PriorityIcon, StateGroupIcon, WorkItemsIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import type { TActivityEntityData, TIssue, TIssueEntityData, TIssuePriorities } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// plane ui
import { calculateTimeAgo, generateWorkItemLink } from "@plane/utils";
// assets
import GitHubInvertocatWhite from "@/app/assets/logos/GitHub_Invertocat_White.png?url";
// components
import { ListItem } from "@/components/core/list";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";

type BlockProps = {
  activity?: TActivityEntityData;
  issue?:
    | (TIssue & { github_issue_number?: number | null; github_repository?: string | null })
    | (TIssueEntityData & { github_issue_number?: number | null; github_repository?: string | null });
  ref?: React.RefObject<HTMLDivElement> | null;
  parentRef?: React.RefObject<HTMLDivElement> | null;
  workspaceSlug: string;
};

type TRecentIssueData = {
  id: string;
  name: string;
  sequence_id?: number | string;
  project_id?: string;
  project_identifier?: string;
  state?: string;
  state_id?: string;
  assignees?: string[];
  assignee_ids?: string[];
  priority?: TIssuePriorities | null;
  type?: string;
  type_id?: string;
  is_epic?: boolean;
  completed_at?: string;
  created_at?: string;
  updated_at?: string;
  github_issue_number?: number | null;
  github_repository?: string | null;
};

export const RecentIssue = observer(function RecentIssue(props: BlockProps) {
  const { activity, issue, ref, parentRef, workspaceSlug } = props;
  const fallbackRef = useRef<HTMLDivElement>(null);
  const resolvedParentRef = parentRef || ref || fallbackRef;

  // hooks
  const { getStateById } = useProjectState();
  const { setPeekIssue } = useIssueDetail();
  const { setPeekIssue: setPeekEpic } = useIssueDetail(EIssueServiceType.EPICS);
  const { getProjectIdentifierById } = useProject();

  // derived values
  const issueDetails = (issue || activity?.entity_data) as TRecentIssueData | undefined;
  if (!issueDetails) return <></>;

  const projectIdentifier = issueDetails.project_id
    ? getProjectIdentifierById(issueDetails.project_id)
    : issueDetails.project_identifier;
  const stateId = issueDetails.state_id || issueDetails.state;
  const state = stateId ? getStateById(stateId) : undefined;
  const assignees = issueDetails.assignee_ids || issueDetails.assignees || [];

  const workItemLink = generateWorkItemLink({
    workspaceSlug: workspaceSlug?.toString(),
    projectId: issueDetails.project_id,
    issueId: issueDetails.id,
    projectIdentifier,
    sequenceId: issueDetails.sequence_id,
    isEpic: issueDetails.is_epic,
  });

  const handlePeekOverview = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!issueDetails.project_id || !issueDetails.id) return;
    const peekDetails = {
      workspaceSlug,
      projectId: issueDetails.project_id,
      issueId: issueDetails.id,
    };
    if (issueDetails.is_epic) setPeekEpic(peekDetails);
    else setPeekIssue(peekDetails);
  };

  const timeText = issueDetails?.completed_at
    ? `Completed ${calculateTimeAgo(issueDetails.completed_at)}`
    : activity?.visited_at
      ? calculateTimeAgo(activity.visited_at)
      : issueDetails?.updated_at
        ? calculateTimeAgo(issueDetails.updated_at)
        : issueDetails?.created_at
          ? calculateTimeAgo(issueDetails.created_at)
          : "";

  return (
    <ListItem
      key={activity?.id || issueDetails?.id}
      id={`issue-${issueDetails?.id}`}
      itemLink={workItemLink}
      title={issueDetails?.name}
      prependTitleElement={
        <div className="flex-shrink-0 flex items-center gap-2">
          {issueDetails?.github_issue_number && issueDetails?.github_repository ? (
            <a
              href={`https://github.com/${issueDetails.github_repository}/issues/${issueDetails.github_issue_number}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 px-2 py-1 rounded bg-layer-2 hover:bg-layer-3 text-secondary hover:text-primary transition-colors cursor-pointer"
              title={`Open GitHub issue #${issueDetails.github_issue_number}`}
            >
              <img src={GitHubInvertocatWhite} alt="GitHub" className="size-3.5 flex-shrink-0 object-contain" />
              <span className="font-medium text-13 whitespace-nowrap">#{issueDetails.github_issue_number}</span>
            </a>
          ) : (
            <div className="flex gap-1.5 items-center justify-center px-2 py-1 rounded bg-layer-2">
              <div className="flex-shrink-0 grid place-items-center rounded-sm size-4">
                <WorkItemsIcon className="size-3.5 text-tertiary" />
              </div>
              <div className="font-medium text-placeholder text-13 whitespace-nowrap">#{issueDetails?.sequence_id}</div>
            </div>
          )}
        </div>
      }
      appendTitleElement={<div className="flex-shrink-0 font-medium text-11 text-placeholder">{timeText}</div>}
      quickActionElement={
        <div className="flex gap-4">
          <Tooltip tooltipHeading="Status" tooltipContent={state?.name ?? "Status"}>
            <div>
              <StateGroupIcon
                stateGroup={state?.group ?? "backlog"}
                color={state?.color}
                className="h-4 w-4 my-auto"
                percentage={state?.order}
              />
            </div>
          </Tooltip>
          <Tooltip tooltipHeading="Priority" tooltipContent={issueDetails?.priority ?? "Priority"}>
            <div>
              <PriorityIcon priority={issueDetails?.priority} withContainer size={12} />
            </div>
          </Tooltip>
          {assignees?.length > 0 && (
            <div className="h-5">
              <MemberDropdown
                projectId={issueDetails?.project_id ?? undefined}
                value={assignees}
                onChange={() => {}}
                disabled
                multiple
                buttonVariant={assignees?.length > 0 ? "transparent-without-text" : "border-without-text"}
                buttonClassName={assignees?.length > 0 ? "hover:bg-transparent px-0" : ""}
                showTooltip={assignees?.length === 0}
                placeholder="Assignees"
                optionsClassName="z-10"
                tooltipContent=""
              />
            </div>
          )}
        </div>
      }
      parentRef={resolvedParentRef}
      disableLink={false}
      className="my-auto !px-2 border-none py-3"
      itemClassName="my-auto"
      onItemClick={handlePeekOverview}
      preventDefaultProgress
    />
  );
});
