/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { BarChart } from "@plane/propel/charts/bar-chart";
import type { TInstanceStorage } from "@plane/types";
// local
import { formatBytes, formatNumber } from "../common/format";
import { PanelCard } from "../common/panel-card";
import { CHART_COLORS } from "../constants";

type Props = { postgres: TInstanceStorage["postgres"] };

/** Database size and the tables accounting for most of it. */
export const PostgresCard = ({ postgres }: Props) => {
  const { t } = useTranslation();

  const data = useMemo(
    () =>
      postgres.largest_tables.slice(0, 10).map((table) => ({
        // Strip the schema prefix; every table here is in `public`.
        name: table.table.replace(/^public\./, ""),
        megabytes: Number((table.total_bytes / 1024 / 1024).toFixed(2)),
      })),
    [postgres.largest_tables]
  );

  return (
    <PanelCard
      title={t("instance_dashboard.storage.postgres")}
      subtitle={t("instance_dashboard.storage.postgres_subtitle", {
        size: formatBytes(postgres.database_size_bytes),
      })}
    >
      <BarChart
        className="h-[300px] w-full"
        data={data}
        bars={[
          {
            key: "megabytes",
            label: t("instance_dashboard.storage.megabytes"),
            stackId: "megabytes",
            fill: CHART_COLORS[0],
            textClassName: "",
          },
        ]}
        xAxis={{ key: "name", label: t("instance_dashboard.storage.table") }}
        yAxis={{ key: "megabytes", label: t("instance_dashboard.storage.megabytes") }}
      />

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="border-b border-subtle text-left text-xs text-tertiary">
              <th className="pb-2 font-medium">{t("instance_dashboard.storage.table")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.storage.total")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.storage.indexes")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.storage.rows_estimate")}</th>
            </tr>
          </thead>
          <tbody>
            {postgres.largest_tables.map((table) => (
              <tr key={table.table} className="border-b border-subtle last:border-0">
                <td className="py-2 font-medium text-secondary">{table.table.replace(/^public\./, "")}</td>
                <td className="py-2 text-right tabular-nums text-tertiary">{formatBytes(table.total_bytes)}</td>
                <td className="py-2 text-right tabular-nums text-tertiary">{formatBytes(table.index_bytes)}</td>
                <td className="py-2 text-right tabular-nums text-tertiary">{formatNumber(table.row_estimate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PanelCard>
  );
};
