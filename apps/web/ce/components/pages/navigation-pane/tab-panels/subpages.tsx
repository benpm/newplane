/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Plus } from "lucide-react";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import { getPageName } from "@plane/utils";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/plane-web/hooks/store";
// store
import type { TPageInstance } from "@/store/pages/base-page";

type Props = {
  page: TPageInstance;
};

export const PageNavigationPaneSubpagesTabPanel = observer(function PageNavigationPaneSubpagesTabPanel(props: Props) {
  const { page } = props;
  const router = useRouter();
  const params = useParams();
  const [isCreating, setIsCreating] = useState(false);

  const workspaceSlug = params.workspaceSlug?.toString();
  const projectId = params.projectId?.toString() || page.project_ids?.[0];

  const { fetchSubPages, getPageChildIds, getPageById, createPage } = usePageStore(EPageStoreType.PROJECT);

  useEffect(() => {
    if (workspaceSlug && projectId && page.id) {
      void fetchSubPages(workspaceSlug, projectId, page.id);
    }
  }, [workspaceSlug, projectId, page.id, fetchSubPages]);

  const childIds = (page?.id ? getPageChildIds(page.id) : []) || [];

  const handleAddSubpage = async () => {
    if (!workspaceSlug || !projectId || !page?.id || isCreating) return;
    try {
      setIsCreating(true);
      const newPage = await createPage({
        name: "Untitled",
        parent: page.id,
      });
      if (newPage?.id) {
        router.push(`/${workspaceSlug}/projects/${projectId}/pages/${newPage.id}`);
      }
    } catch (error) {
      console.error("Failed to create subpage", error);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="size-full pt-3 flex flex-col gap-3">
      <div className="flex items-center justify-between px-1">
        <span className="text-12 font-semibold text-secondary">Subpages ({childIds.length})</span>
        <Tooltip tooltipContent="Add subpage">
          <button
            type="button"
            onClick={() => {
              void handleAddSubpage();
            }}
            disabled={isCreating}
            className="flex items-center gap-1 text-12 font-medium text-secondary hover:text-primary transition-colors disabled:opacity-50"
            aria-label="Add subpage"
          >
            <Plus className="size-3.5" />
            <span>Add</span>
          </button>
        </Tooltip>
      </div>

      {childIds.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-6 text-center text-placeholder gap-2 my-auto">
          <div className="grid size-10 place-items-center rounded bg-layer-2">
            <PageIcon className="size-5 text-tertiary" />
          </div>
          <p className="text-13 font-medium text-secondary">No subpages yet</p>
          <p className="text-11 text-placeholder max-w-[200px]">Subpages created under this page will appear here.</p>
          <button
            type="button"
            onClick={() => {
              void handleAddSubpage();
            }}
            disabled={isCreating}
            className="mt-2 px-3 py-1.5 text-12 font-medium bg-layer-2 hover:bg-layer-3 text-secondary hover:text-primary rounded border border-subtle transition-colors"
          >
            {isCreating ? "Creating..." : "Create subpage"}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-1 overflow-y-auto vertical-scrollbar scrollbar-sm">
          {childIds.map((childId) => {
            const childPage = getPageById(childId);
            if (!childPage) return null;
            const subpagesCount = childPage.sub_pages_count ?? 0;

            return (
              <Link
                key={childId}
                href={`/${workspaceSlug}/projects/${projectId}/pages/${childId}`}
                className="group flex items-center justify-between gap-2 p-2 rounded hover:bg-layer-1 transition-colors text-secondary hover:text-primary"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="shrink-0 size-4 grid place-items-center">
                    {childPage.logo_props?.in_use ? (
                      <Logo logo={childPage.logo_props} size={14} type="lucide" />
                    ) : (
                      <PageIcon className="size-3.5 text-tertiary" />
                    )}
                  </div>
                  <span className="truncate text-13 font-medium">{getPageName(childPage.name)}</span>
                </div>
                {subpagesCount > 0 && (
                  <span className="shrink-0 px-1.5 py-0.5 rounded text-10 font-semibold bg-layer-2 text-placeholder">
                    {subpagesCount}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
});
