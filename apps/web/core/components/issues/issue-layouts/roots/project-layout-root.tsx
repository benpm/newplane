/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useSearchParams } from "react-router";
import { Filter, X } from "lucide-react";
import useSWR from "swr";
// plane constants
import { EIssueFilterType, ISSUE_DISPLAY_FILTERS_BY_PAGE, PROJECT_VIEW_TRACKER_ELEMENTS } from "@plane/constants";
import type { IWorkItemFilterInstance } from "@plane/shared-state";
import { EIssueLayoutTypes, EIssuesStoreType } from "@plane/types";
import { Spinner } from "@plane/ui";
// components
import { ProjectLevelWorkItemFiltersHOC } from "@/components/work-item-filters/filters-hoc/project-level";
import { WorkItemFiltersRow } from "@/components/work-item-filters/filters-row";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useUser } from "@/hooks/store/user";
import { IssuesStoreContext } from "@/hooks/use-issue-layout-store";
// local imports
import { IssuePeekOverview } from "../../peek-overview";
import { CalendarLayout } from "../calendar/roots/project-root";
import { BaseGanttRoot } from "../gantt";
import { KanBanLayout } from "../kanban/roots/project-root";
import { ListLayout } from "../list/roots/project-root";
import { ProjectSpreadsheetLayout } from "../spreadsheet/roots/project-root";

function ProjectIssueLayout(props: { activeLayout: EIssueLayoutTypes | undefined }) {
  switch (props.activeLayout) {
    case EIssueLayoutTypes.LIST:
      return <ListLayout />;
    case EIssueLayoutTypes.KANBAN:
      return <KanBanLayout />;
    case EIssueLayoutTypes.CALENDAR:
      return <CalendarLayout />;
    case EIssueLayoutTypes.GANTT:
      return <BaseGanttRoot />;
    case EIssueLayoutTypes.SPREADSHEET:
      return <ProjectSpreadsheetLayout />;
    default:
      return null;
  }
}

interface IProjectLayoutContentProps {
  projectWorkItemsFilter: IWorkItemFilterInstance | undefined;
  activeLayout: EIssueLayoutTypes | undefined;
}

const ProjectLayoutContent = observer(function ProjectLayoutContent(props: IProjectLayoutContentProps) {
  const { projectWorkItemsFilter, activeLayout } = props;
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: currentUser } = useUser();
  const { issues } = useIssues(EIssuesStoreType.PROJECT);

  const isUserFilter = searchParams.get("user_filter") === "true";
  const [userFilterDismissed, setUserFilterDismissed] = useState(false);
  const userFilterAppliedRef = useRef(false);

  // If user_filter in URL changes to true, reset dismissed state and applied ref
  useEffect(() => {
    if (isUserFilter) {
      setUserFilterDismissed(false);
      userFilterAppliedRef.current = false;
    }
  }, [isUserFilter]);

  // When user_filter is requested, ensure the assignee filter is applied
  useEffect(() => {
    if (!isUserFilter || userFilterDismissed || !currentUser?.id || !projectWorkItemsFilter) {
      return;
    }
    if (userFilterAppliedRef.current) return;

    const existingCondition = projectWorkItemsFilter.findFirstConditionByPropertyAndOperator("assignee_id", "in");
    const isAlreadyAssigned =
      existingCondition &&
      Array.isArray(existingCondition.value) &&
      (existingCondition.value as string[]).includes(currentUser.id);

    if (!isAlreadyAssigned) {
      userFilterAppliedRef.current = true;
      projectWorkItemsFilter.addCondition(
        "and",
        {
          property: "assignee_id",
          operator: "in",
          value: [currentUser.id],
        },
        false
      );
    } else {
      userFilterAppliedRef.current = true;
    }
  }, [isUserFilter, userFilterDismissed, currentUser?.id, projectWorkItemsFilter]);

  const userCondition = projectWorkItemsFilter?.findFirstConditionByPropertyAndOperator("assignee_id", "in");
  const hasUserCondition = Boolean(userCondition);

  const handleClearUserFilter = useCallback(() => {
    if (projectWorkItemsFilter) {
      const condition = projectWorkItemsFilter.findFirstConditionByPropertyAndOperator("assignee_id", "in");
      if (condition) {
        projectWorkItemsFilter.removeCondition(condition.id);
      }
    }
    setUserFilterDismissed(true);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("user_filter");
        return next;
      },
      { replace: true }
    );
  }, [projectWorkItemsFilter, setSearchParams]);

  const showBanner = isUserFilter && !userFilterDismissed && hasUserCondition;

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden">
      {projectWorkItemsFilter && (
        <WorkItemFiltersRow
          filter={projectWorkItemsFilter}
          trackerElements={{
            saveView: PROJECT_VIEW_TRACKER_ELEMENTS.PROJECT_HEADER_SAVE_AS_VIEW_BUTTON,
          }}
        />
      )}
      {showBanner && (
        <div className="flex items-center justify-between px-4 py-2 bg-primary/10 border-b border-primary/20 text-xs text-primary font-medium transition-all">
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="font-semibold">Filtered to your assigned work items</span>
            <span className="text-placeholder">•</span>
            <span className="text-secondary">Turn off this filter to see all work items in this project</span>
          </div>
          <button
            type="button"
            onClick={handleClearUserFilter}
            className="inline-flex items-center gap-1 font-semibold text-primary hover:text-primary-hover hover:underline cursor-pointer transition-colors"
          >
            <span>Turn off filter</span>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <div className="relative h-full w-full overflow-auto bg-surface-1">
        {/* mutation loader */}
        {issues?.getIssueLoader() === "mutation" && (
          <div className="fixed w-[40px] h-[40px] z-50 right-[20px] top-[70px] flex justify-center items-center bg-layer-1 shadow-sm rounded-sm">
            <Spinner className="w-4 h-4" />
          </div>
        )}
        <ProjectIssueLayout activeLayout={activeLayout} />
      </div>
      {/* peek overview */}
      <IssuePeekOverview />
    </div>
  );
});

export const ProjectLayoutRoot = observer(function ProjectLayoutRoot() {
  // router
  const { workspaceSlug: routerWorkspaceSlug, projectId: routerProjectId } = useParams();
  const workspaceSlug = routerWorkspaceSlug ? routerWorkspaceSlug.toString() : undefined;
  const projectId = routerProjectId ? routerProjectId.toString() : undefined;
  const [searchParams] = useSearchParams();
  const layoutParam = searchParams.get("layout");
  // hooks
  const { issuesFilter } = useIssues(EIssuesStoreType.PROJECT);
  // derived values
  const workItemFilters = projectId ? issuesFilter?.getIssueFilters(projectId) : undefined;

  useSWR(
    workspaceSlug && projectId ? `PROJECT_ISSUES_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId) {
        await issuesFilter?.fetchFilters(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  // Switch layout to Kanban if layout=kanban is requested in query params
  useEffect(() => {
    if (!workspaceSlug || !projectId) return;
    if (layoutParam === "kanban" && workItemFilters?.displayFilters?.layout !== EIssueLayoutTypes.KANBAN) {
      void issuesFilter?.updateFilters(workspaceSlug, projectId, EIssueFilterType.DISPLAY_FILTERS, {
        layout: EIssueLayoutTypes.KANBAN,
      });
    }
  }, [workspaceSlug, projectId, layoutParam, workItemFilters?.displayFilters?.layout, issuesFilter]);

  const effectiveLayout =
    layoutParam === "kanban"
      ? EIssueLayoutTypes.KANBAN
      : (workItemFilters?.displayFilters?.layout ?? EIssueLayoutTypes.KANBAN);

  const effectiveWorkItemFilters = useMemo(() => {
    if (!workItemFilters) return undefined;
    if (layoutParam === "kanban" && workItemFilters.displayFilters?.layout !== EIssueLayoutTypes.KANBAN) {
      return {
        ...workItemFilters,
        displayFilters: {
          ...workItemFilters.displayFilters,
          layout: EIssueLayoutTypes.KANBAN,
        },
      };
    }
    return workItemFilters;
  }, [workItemFilters, layoutParam]);

  if (!workspaceSlug || !projectId || !workItemFilters) return <></>;
  return (
    <IssuesStoreContext.Provider value={EIssuesStoreType.PROJECT}>
      <ProjectLevelWorkItemFiltersHOC
        enableSaveView
        entityType={EIssuesStoreType.PROJECT}
        entityId={projectId}
        filtersToShowByLayout={ISSUE_DISPLAY_FILTERS_BY_PAGE.issues.filters}
        initialWorkItemFilters={effectiveWorkItemFilters}
        updateFilters={(filters) => {
          if (issuesFilter) {
            void issuesFilter.updateFilterExpression(workspaceSlug, projectId, filters);
          }
        }}
        projectId={projectId}
        workspaceSlug={workspaceSlug}
      >
        {({ filter: projectWorkItemsFilter }) => (
          <ProjectLayoutContent projectWorkItemsFilter={projectWorkItemsFilter} activeLayout={effectiveLayout} />
        )}
      </ProjectLevelWorkItemFiltersHOC>
    </IssuesStoreContext.Provider>
  );
});
