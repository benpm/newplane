/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
// plane imports
import type { TMentionSection, TPageLinkHandler, TPageLinkSuggestion } from "@plane/editor";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
import type { TSearchEntityRequestPayload, TSearchResponse } from "@plane/types";
import { getPageName } from "@plane/utils";

type TArgs = {
  workspaceSlug: string;
  projectId: string | undefined;
  /** omit (e.g. for read-only editors) to disable page-link autocomplete */
  searchEntity: ((payload: TSearchEntityRequestPayload) => Promise<TSearchResponse>) | undefined;
};

/**
 * Page search for the editor's `[` page-link autocomplete. Returns undefined — disabling the
 * extension — when there is no project to search in.
 */
export const usePageLinkHandler = (args: TArgs): TPageLinkHandler | undefined => {
  const { workspaceSlug, projectId, searchEntity } = args;
  const { t } = useTranslation();

  return useMemo(() => {
    if (!projectId || !searchEntity) return undefined;
    return {
      searchCallback: async (query: string): Promise<TMentionSection[]> => {
        const res = await searchEntity({ count: 10, query_type: ["page"], query, project_id: projectId });
        const items: TPageLinkSuggestion[] = (res?.page ?? []).flatMap(({ id, name }) =>
          id
            ? [
                {
                  id,
                  entity_identifier: id,
                  entity_name: "page" as const,
                  title: getPageName(name ?? ""),
                  icon: <PageIcon className="size-3.5 text-tertiary" />,
                  // search results are scoped to projectId, so the page always lives there
                  redirect_uri: `/${workspaceSlug}/projects/${projectId}/pages/${id}`,
                },
              ]
            : []
        );
        return items.length > 0 ? [{ key: "pages", title: t("sidebar.pages"), items }] : [];
      },
    };
  }, [projectId, searchEntity, t, workspaceSlug]);
};
