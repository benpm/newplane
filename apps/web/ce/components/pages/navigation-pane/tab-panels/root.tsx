/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPageInstance } from "@/store/pages/base-page";
// local imports
import type { TPageNavigationPaneTab } from "..";
import { PageNavigationPaneSubpagesTabPanel } from "./subpages";

export type TPageNavigationPaneAdditionalTabPanelsRootProps = {
  activeTab: TPageNavigationPaneTab;
  page: TPageInstance;
};

export function PageNavigationPaneAdditionalTabPanelsRoot(props: TPageNavigationPaneAdditionalTabPanelsRootProps) {
  const { activeTab, page } = props;

  if (activeTab === "subpages") {
    return <PageNavigationPaneSubpagesTabPanel page={page} />;
  }

  return null;
}
