/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { InstanceDashboardService } from "@plane/services";
import { Loader } from "@plane/ui";
// local
import { SWR_KEY } from "../constants";
import { CountsGrid } from "./counts-grid";
import { InstanceInfoCard } from "./instance-info-card";
import { WorkItemsStateChart } from "./work-items-state-chart";

const service = new InstanceDashboardService();

/** Instance-wide entity counts. */
export const OverviewPanel = () => {
  const { t } = useTranslation();
  const { data, isLoading, error } = useSWR(SWR_KEY.OVERVIEW, () => service.fetchOverview());

  if (isLoading) {
    return (
      <Loader className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 12 }).map((_, index) => (
          <Loader.Item key={index} height="88px" />
        ))}
      </Loader>
    );
  }

  if (error || !data) {
    return <p className="text-sm text-danger-primary">{t("instance_dashboard.panel_error")}</p>;
  }

  return (
    <div className="space-y-4">
      <CountsGrid overview={data} />
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <WorkItemsStateChart byStateGroup={data.work_items.by_state_group} />
        </div>
        <InstanceInfoCard />
      </div>
    </div>
  );
};
