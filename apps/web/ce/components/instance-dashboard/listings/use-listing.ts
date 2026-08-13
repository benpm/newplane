/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import useSWR from "swr";
// plane imports
import type { TDashboardPaginated } from "@plane/types";
// local
import { SEARCH_DEBOUNCE_MS } from "../constants";

/**
 * Search + cursor pagination for one inventory table.
 *
 * The SWR key includes the search term and cursor, so each page is cached
 * separately and going back is instant. Typing is debounced so a request is
 * not fired per keystroke.
 */
export const useListing = <T>(
  key: string,
  fetcher: (params: Record<string, string>) => Promise<TDashboardPaginated<T>>
) => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [cursor, setCursor] = useState<string | undefined>(undefined);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  /**
   * A new search invalidates the cursor — it points into the previous result
   * set. Cleared here rather than in an effect on `debouncedSearch`, which
   * would be a synchronous setState in an effect and re-render twice.
   */
  const onSearchChange = (value: string) => {
    setSearch(value);
    setCursor(undefined);
  };

  const { data, isLoading, error, mutate } = useSWR([key, debouncedSearch, cursor], () => {
    const params: Record<string, string> = {};
    if (debouncedSearch) params.search = debouncedSearch;
    if (cursor) params.cursor = cursor;
    return fetcher(params);
  });

  return {
    rows: data?.results ?? [],
    totalCount: data?.total_count,
    isLoading,
    error,
    search,
    setSearch: onSearchChange,
    hasNext: Boolean(data?.next_page_results),
    hasPrev: Boolean(data?.prev_page_results),
    goNext: () => setCursor(data?.next_cursor),
    goPrev: () => setCursor(data?.prev_cursor),
    /** Re-fetch the current page after a mutation. */
    refresh: () => void mutate(),
  };
};
