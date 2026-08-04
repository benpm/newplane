/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { ChevronRight } from "lucide-react";
import { Link, useLocation, useParams } from "react-router";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import { cn, getPageName } from "@plane/utils";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/plane-web/hooks/store";

type TNodeProps = {
  pageId: string;
  workspaceSlug: string;
  projectId: string;
  level: number;
};

const SidebarPageNode = observer(function SidebarPageNode(props: TNodeProps) {
  const { pageId, workspaceSlug, projectId, level } = props;
  const [isExpanded, setIsExpanded] = useState(false);
  const { pathname } = useLocation();
  const { getPageById, getPageChildIds, fetchSubPages } = usePageStore(EPageStoreType.PROJECT);

  const page = getPageById(pageId);
  if (!page) return null;

  const hasChildren = (page.sub_pages_count ?? 0) > 0;
  const childIds = isExpanded ? getPageChildIds(pageId) : [];
  const href = `/${workspaceSlug}/projects/${projectId}/pages/${pageId}`;
  const isActive = pathname.includes(pageId);

  const handleToggleExpand = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    const next = !isExpanded;
    setIsExpanded(next);
    if (next) void fetchSubPages(workspaceSlug, projectId, pageId);
  };

  return (
    <>
      <Link
        to={href}
        className={cn(
          "flex items-center gap-1 rounded py-1 pr-1 text-11 font-medium text-secondary hover:bg-layer-1-hover",
          isActive && "bg-layer-1 text-primary"
        )}
        style={{ paddingLeft: `${0.5 + level * 0.75}rem` }}
      >
        <button
          type="button"
          onClick={handleToggleExpand}
          aria-expanded={isExpanded}
          className={cn("grid size-4 flex-shrink-0 place-items-center rounded", !hasChildren && "invisible")}
          tabIndex={hasChildren ? 0 : -1}
        >
          <ChevronRight className={cn("size-3 text-tertiary transition-transform", isExpanded && "rotate-90")} />
        </button>
        {page.logo_props?.in_use ? (
          <Logo logo={page.logo_props} size={12} type="lucide" />
        ) : (
          <PageIcon className="size-3.5 flex-shrink-0 text-tertiary" />
        )}
        <span className="truncate">{getPageName(page.name)}</span>
      </Link>
      {isExpanded &&
        childIds.map((childId) => (
          <SidebarPageNode
            key={childId}
            pageId={childId}
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            level={level + 1}
          />
        ))}
    </>
  );
});

type TTreeProps = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Nested page tree shown under the "Pages" sidebar entry while the user is inside the
 * project's pages section. Roots come from the pages list; children load on expand.
 */
export const SidebarProjectPagesTree = observer(function SidebarProjectPagesTree(props: TTreeProps) {
  const { workspaceSlug, projectId } = props;
  const { pathname } = useLocation();
  const params = useParams();
  const { getCurrentProjectFilteredPageIdsByTab, fetchPagesList } = usePageStore(EPageStoreType.PROJECT);

  const isInPagesSection = pathname.includes(`/projects/${projectId}/pages`) && params.projectId === projectId;

  useEffect(() => {
    if (isInPagesSection) void fetchPagesList(workspaceSlug, projectId, "public");
  }, [isInPagesSection, fetchPagesList, workspaceSlug, projectId]);

  if (!isInPagesSection) return null;

  const rootPageIds = getCurrentProjectFilteredPageIdsByTab("public") ?? [];
  if (rootPageIds.length === 0) return null;

  return (
    <div className="flex flex-col gap-0.5 pl-4">
      {rootPageIds.map((pageId) => (
        <SidebarPageNode key={pageId} pageId={pageId} workspaceSlug={workspaceSlug} projectId={projectId} level={0} />
      ))}
    </div>
  );
});
