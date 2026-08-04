/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
// plane imports
import { PageIcon } from "@plane/propel/icons";
import { Breadcrumbs } from "@plane/ui";
import { getPageName } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// plane web hooks
import type { EPageStoreType } from "@/plane-web/hooks/store";
import { usePageStore } from "@/plane-web/hooks/store";
// store
import type { TPageInstance } from "@/store/pages/base-page";

type Props = {
  page: TPageInstance;
  storeType: EPageStoreType;
  workspaceSlug: string;
  projectId: string;
};

/**
 * Breadcrumb items for a page's ancestor chain (root -> ... -> direct parent).
 * Ancestors already in the store render immediately; missing ones are fetched by id.
 */
export const PageAncestorBreadcrumbs = observer(function PageAncestorBreadcrumbs(props: Props) {
  const { page, storeType, workspaceSlug, projectId } = props;
  const { getPageById, fetchPageDetails } = usePageStore(storeType);

  // Walk up from the direct parent. Stops on missing (not yet fetched) ancestors and
  // guards against cycles with a visited-set.
  const ancestors: TPageInstance[] = [];
  const visited = new Set<string>();
  let currentParentId = page.parent ?? null;
  let missingAncestorId: string | null = null;
  while (currentParentId && !visited.has(currentParentId)) {
    visited.add(currentParentId);
    const ancestor = getPageById(currentParentId);
    if (!ancestor) {
      missingAncestorId = currentParentId;
      break;
    }
    ancestors.unshift(ancestor);
    currentParentId = ancestor.parent ?? null;
  }

  useEffect(() => {
    if (missingAncestorId) {
      void fetchPageDetails(workspaceSlug, projectId, missingAncestorId, { trackVisit: false }).catch(() => {
        // ancestor may be inaccessible (private); the chain simply renders shorter
      });
    }
  }, [missingAncestorId, fetchPageDetails, workspaceSlug, projectId]);

  if (ancestors.length === 0) return null;

  return (
    <>
      {ancestors.map((ancestor) => (
        <Breadcrumbs.Item
          key={ancestor.id}
          component={
            <BreadcrumbLink
              label={getPageName(ancestor.name)}
              href={`/${workspaceSlug}/projects/${projectId}/pages/${ancestor.id}`}
              icon={<PageIcon className="h-4 w-4 text-tertiary" />}
            />
          }
        />
      ))}
    </>
  );
});
