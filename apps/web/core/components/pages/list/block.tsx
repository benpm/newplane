/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import { observer } from "mobx-react";
import { ChevronRight } from "lucide-react";
import { useParams } from "react-router";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
// plane imports
import { cn, getPageName } from "@plane/utils";
// components
import { ListItem } from "@/components/core/list";
import { BlockItemAction } from "@/components/pages/list/block-item-action";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web hooks
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePage, usePageStore } from "@/plane-web/hooks/store";

type TPageListBlock = {
  pageId: string;
  storeType: EPageStoreType;
  /** nesting depth; 0 for root pages */
  level?: number;
};

export const PageListBlock = observer(function PageListBlock(props: TPageListBlock) {
  const { pageId, storeType, level = 0 } = props;
  // states
  const [isExpanded, setIsExpanded] = useState(false);
  const [isFetchingChildren, setIsFetchingChildren] = useState(false);
  // refs
  const parentRef = useRef(null);
  // router
  const { workspaceSlug, projectId } = useParams();
  // hooks
  const page = usePage({
    pageId,
    storeType,
  });
  const { fetchSubPages, getPageChildIds } = usePageStore(storeType);
  const { isMobile } = usePlatformOS();
  // handle page check
  if (!page) return null;
  // derived values
  const { name, logo_props, sub_pages_count, getRedirectionLink } = page;
  const hasChildren = (sub_pages_count ?? 0) > 0;
  const childIds = isExpanded ? getPageChildIds(pageId) : [];

  const handleToggleExpand = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    const next = !isExpanded;
    setIsExpanded(next);
    // children may already be in the store (e.g. after navigation); refetch is cheap and keeps counts fresh
    if (next && workspaceSlug && projectId) {
      setIsFetchingChildren(true);
      void fetchSubPages(workspaceSlug.toString(), projectId.toString(), pageId).finally(() =>
        setIsFetchingChildren(false)
      );
    }
  };

  return (
    <>
      <ListItem
        prependTitleElement={
          <span className="flex items-center gap-1" style={{ marginLeft: `${level * 1.25}rem` }}>
            <button
              type="button"
              onClick={handleToggleExpand}
              aria-expanded={isExpanded}
              className={cn(
                "grid size-5 flex-shrink-0 place-items-center rounded hover:bg-layer-1-hover",
                !hasChildren && "invisible"
              )}
              tabIndex={hasChildren ? 0 : -1}
            >
              <ChevronRight className={cn("size-3.5 text-tertiary transition-transform", isExpanded && "rotate-90")} />
            </button>
            {logo_props?.in_use ? (
              <Logo logo={logo_props} size={16} type="lucide" />
            ) : (
              <PageIcon className="h-4 w-4 text-tertiary" />
            )}
          </span>
        }
        title={getPageName(name)}
        itemLink={getRedirectionLink()}
        actionableItems={<BlockItemAction page={page} parentRef={parentRef} storeType={storeType} />}
        isMobile={isMobile}
        parentRef={parentRef}
      />
      {isExpanded &&
        !isFetchingChildren &&
        childIds.map((childId) => (
          <PageListBlock key={childId} pageId={childId} storeType={storeType} level={level + 1} />
        ))}
    </>
  );
});
