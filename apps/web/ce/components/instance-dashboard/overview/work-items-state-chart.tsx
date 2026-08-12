/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { BarChart } from "@plane/propel/charts/bar-chart";
// local
import { PanelCard } from "../common/panel-card";
import { STATE_GROUP_COLORS } from "../constants";

type Props = { byStateGroup: Record<string, number> };

/** Work items bucketed by state group. */
export const WorkItemsStateChart = ({ byStateGroup }: Props) => {
  const { t } = useTranslation();

  const data = useMemo(
    () =>
      Object.entries(byStateGroup)
        .filter(([, count]) => count > 0)
        .map(([group, count]) => ({
          name: t(`instance_dashboard.state_group.${group}`, { defaultValue: group }),
          count,
          // Per-bar colour is not something the shared BarChart supports, so
          // the group colour rides along for the legend beneath the chart.
          fill: STATE_GROUP_COLORS[group] ?? STATE_GROUP_COLORS.none,
        })),
    [byStateGroup, t]
  );

  return (
    <PanelCard title={t("instance_dashboard.overview.state_distribution")}>
      {data.length === 0 ? (
        <p className="text-sm text-tertiary">{t("instance_dashboard.overview.no_work_items")}</p>
      ) : (
        <BarChart
          className="h-[280px] w-full"
          data={data}
          bars={[
            {
              key: "count",
              label: t("instance_dashboard.counts.work_items"),
              stackId: "count",
              fill: STATE_GROUP_COLORS.unstarted,
              textClassName: "",
            },
          ]}
          xAxis={{ key: "name", label: t("instance_dashboard.overview.state_group") }}
          yAxis={{ key: "count", label: t("instance_dashboard.counts.work_items"), allowDecimals: false }}
        />
      )}
    </PanelCard>
  );
};
