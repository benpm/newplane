/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useSWRConfig } from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { cn } from "@plane/utils";
// local
import { DASHBOARD_TABS, SWR_KEY_PREFIX, type TDashboardTab } from "./constants";
import { HealthPanel } from "./health/health-panel";
import { ListingsPanel } from "./listings/listings-panel";
import { OverviewPanel } from "./overview/overview-panel";
import { StoragePanel } from "./storage/storage-panel";

/** The instance dashboard: health, counts, storage and inventories. */
export const InstanceDashboardRoot = () => {
  const { t } = useTranslation();
  const { mutate } = useSWRConfig();
  const [tab, setTab] = useState<TDashboardTab>("health");

  /** Revalidate every dashboard query at once, whichever tab is showing. */
  const refreshAll = () =>
    void mutate((key) => {
      const head = Array.isArray(key) ? key[0] : key;
      return typeof head === "string" && head.startsWith(SWR_KEY_PREFIX);
    });

  return (
    <div className="flex size-full flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-4 border-b border-subtle px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-primary">{t("instance_dashboard.title")}</h1>
          <p className="text-xs text-tertiary">{t("instance_dashboard.subtitle")}</p>
        </div>
        <Button variant="secondary" size="sm" prependIcon={<RefreshCw className="size-3.5" />} onClick={refreshAll}>
          {t("instance_dashboard.refresh")}
        </Button>
      </div>

      <div className="flex gap-1 border-b border-subtle px-6">
        {DASHBOARD_TABS.map((dashboardTab) => (
          <button
            key={dashboardTab}
            type="button"
            onClick={() => setTab(dashboardTab)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
              tab === dashboardTab
                ? "border-brand-primary text-primary"
                : "border-transparent text-tertiary hover:text-secondary"
            )}
          >
            {t(`instance_dashboard.tab.${dashboardTab}`)}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {tab === "health" && <HealthPanel />}
        {tab === "overview" && <OverviewPanel />}
        {tab === "storage" && <StoragePanel />}
        {tab === "inventory" && <ListingsPanel />}
      </div>
    </div>
  );
};
