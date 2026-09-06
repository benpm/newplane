/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane types
import { WorkItemsIcon } from "@plane/propel/icons";
import type { TActivityEntityData, THomeWidgetProps, TIssue } from "@plane/types";
// hooks
import { useUser } from "@/hooks/store/user";
// components
import { ContentOverflowWrapper } from "@/components/core/content-overflow-HOC";
// plane web services
import { WorkspaceService } from "@/services/workspace.service";
import { EWidgetKeys, WidgetLoader } from "../loaders";
import { FiltersDropdown, type TFilterOption } from "./filters";
import { RecentIssue } from "./issue";
import { RecentPage } from "./page";
import { RecentProject } from "./project";

const WIDGET_KEY = EWidgetKeys.RECENT_ACTIVITY;
const LOCAL_STORAGE_KEY = "plane_home_work_items_filter";
const workspaceService = new WorkspaceService();

const HOME_WORK_ITEMS_FILTERS: TFilterOption[] = [
  { name: "unassigned", label: "Unassigned work items", icon: <WorkItemsIcon className="w-4 h-4" /> },
  { name: "assigned", label: "Your assigned work items", icon: <WorkItemsIcon className="w-4 h-4" /> },
  { name: "finished", label: "Finished items (by completion date)", icon: <WorkItemsIcon className="w-4 h-4" /> },
  { name: "recent", label: "Recently visited", icon: <WorkItemsIcon className="w-4 h-4" /> },
];

type TRecentWidgetProps = THomeWidgetProps & {
  presetFilter?: string;
  showFilterSelect?: boolean;
};

export const RecentActivityWidget = observer(function RecentActivityWidget(props: TRecentWidgetProps) {
  const { presetFilter, showFilterSelect = true, workspaceSlug } = props;
  const { data: currentUser } = useUser();

  // states
  const [filter, setFilter] = useState<string>(() => {
    if (presetFilter) return presetFilter;
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved && ["unassigned", "assigned", "finished", "recent"].includes(saved)) {
        return saved;
      }
    }
    return "unassigned";
  });

  const handleFilterChange = (newFilter: string) => {
    setFilter(newFilter);
    if (typeof window !== "undefined") {
      localStorage.setItem(LOCAL_STORAGE_KEY, newFilter);
    }
  };

  // ref
  const ref = useRef<HTMLDivElement>(null);

  const isViewIssuesFilter = filter === "unassigned" || filter === "assigned" || filter === "finished";

  const { data: issuesData, isLoading: isIssuesLoading } = useSWR(
    workspaceSlug && isViewIssuesFilter
      ? `WORKSPACE_HOME_ISSUES_${workspaceSlug.toString()}_${filter}_${currentUser?.id ?? ""}`
      : null,
    async () => {
      if (filter === "unassigned") {
        return workspaceService.getViewIssues(workspaceSlug.toString(), {
          assignees: "None",
          order_by: "-created_at",
          per_page: 30,
        });
      }
      if (filter === "assigned") {
        if (!currentUser?.id) return { results: [] };
        return workspaceService.getViewIssues(workspaceSlug.toString(), {
          assignees: currentUser.id,
          order_by: "-updated_at",
          per_page: 30,
        });
      }
      if (filter === "finished") {
        return workspaceService.getViewIssues(workspaceSlug.toString(), {
          state_group: "completed",
          order_by: "-completed_at",
          per_page: 30,
        });
      }
      return { results: [] };
    },
    {
      revalidateIfStale: false,
      revalidateOnFocus: true,
      revalidateOnReconnect: false,
    }
  );

  const { data: recents, isLoading: isRecentsLoading } = useSWR(
    workspaceSlug && filter === "recent" ? `WORKSPACE_RECENT_ACTIVITY_${workspaceSlug.toString()}_recent` : null,
    () => workspaceService.fetchWorkspaceRecents(workspaceSlug.toString(), "issue"),
    {
      revalidateIfStale: false,
      revalidateOnFocus: true,
      revalidateOnReconnect: false,
    }
  );

  const isLoading = isViewIssuesFilter ? isIssuesLoading : isRecentsLoading;

  type THomeIssue = TIssue & { github_issue_number?: number | null; github_repository?: string | null };

  const issuesList = useMemo<THomeIssue[]>(() => {
    if (isViewIssuesFilter) {
      if (!issuesData?.results) return [];
      return (
        Array.isArray(issuesData.results) ? issuesData.results : Object.values(issuesData.results)
      ) as THomeIssue[];
    }
    return [];
  }, [isViewIssuesFilter, issuesData]);

  const isEmpty = !isLoading && (isViewIssuesFilter ? issuesList.length === 0 : !recents || recents.length === 0);

  const emptyMessage =
    filter === "unassigned"
      ? "No unassigned work items"
      : filter === "assigned"
        ? "No work items assigned to you"
        : filter === "finished"
          ? "No finished work items"
          : "No recent activity";

  const resolveRecent = (activity: TActivityEntityData) => {
    switch (activity.entity_name) {
      case "page":
      case "workspace_page":
        return <RecentPage activity={activity} ref={ref} workspaceSlug={workspaceSlug.toString()} />;
      case "project":
        return <RecentProject activity={activity} ref={ref} workspaceSlug={workspaceSlug.toString()} />;
      case "issue":
        return <RecentIssue activity={activity} ref={ref} workspaceSlug={workspaceSlug.toString()} />;
      default:
        return <></>;
    }
  };

  if (isEmpty)
    return (
      <div ref={ref} className="max-h-[500px] overflow-y-scroll">
        <div className="flex items-center justify-between mb-4">
          <div className="text-14 font-semibold text-tertiary">Work items</div>
          {showFilterSelect && (
            <FiltersDropdown
              filters={HOME_WORK_ITEMS_FILTERS}
              activeFilter={filter}
              setActiveFilter={handleFilterChange}
            />
          )}
        </div>
        <div className="flex flex-col items-center justify-center p-8 text-center text-placeholder">
          <WorkItemsIcon className="size-8 mb-2 text-tertiary" />
          <div className="text-13 font-medium">{emptyMessage}</div>
        </div>
      </div>
    );

  return (
    <ContentOverflowWrapper
      maxHeight={415}
      containerClassName="box-border min-h-[250px]"
      fallback={<></>}
      buttonClassName="bg-surface-2/20"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-14 font-semibold text-tertiary">Work items</div>
        {showFilterSelect && (
          <FiltersDropdown
            filters={HOME_WORK_ITEMS_FILTERS}
            activeFilter={filter}
            setActiveFilter={handleFilterChange}
          />
        )}
      </div>
      <div className="min-h-[250px] flex flex-col">
        {isLoading && <WidgetLoader widgetKey={WIDGET_KEY} />}
        {!isLoading &&
          isViewIssuesFilter &&
          issuesList.map((item) => (
            <div key={item.id}>
              <RecentIssue issue={item} ref={ref} workspaceSlug={workspaceSlug.toString()} />
            </div>
          ))}
        {!isLoading &&
          !isViewIssuesFilter &&
          recents
            ?.filter((recent) => recent.entity_data)
            .map((activity) => <div key={activity.id}>{resolveRecent(activity)}</div>)}
      </div>
    </ContentOverflowWrapper>
  );
});
