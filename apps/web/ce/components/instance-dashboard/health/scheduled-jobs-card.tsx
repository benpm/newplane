/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import { InstanceDashboardService } from "@plane/services";
// local
import { formatDuration } from "../common/format";
import { PanelCard } from "../common/panel-card";
import { SWR_KEY } from "../constants";

const service = new InstanceDashboardService();

/**
 * Celery beat schedule.
 *
 * `last_run_at` is the only evidence beat is alive — this instance has no
 * Celery result backend, so there is no task history to show.
 */
export const ScheduledJobsCard = () => {
  const { t } = useTranslation();
  const { data, isLoading, error } = useSWR(SWR_KEY.JOBS, () => service.fetchScheduledJobs());
  const jobs = data?.results ?? [];

  return (
    <PanelCard
      title={t("instance_dashboard.health.jobs.title")}
      subtitle={t("instance_dashboard.health.jobs.subtitle")}
      isLoading={isLoading}
      error={error}
    >
      {jobs.length === 0 ? (
        <p className="text-sm text-tertiary">{t("instance_dashboard.health.jobs.none")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-subtle text-left text-xs text-tertiary">
                <th className="pb-2 font-medium">{t("instance_dashboard.health.jobs.name")}</th>
                <th className="pb-2 font-medium">{t("instance_dashboard.health.jobs.schedule")}</th>
                <th className="pb-2 text-right font-medium">{t("instance_dashboard.health.jobs.last_run")}</th>
                <th className="pb-2 text-right font-medium">{t("instance_dashboard.health.jobs.runs")}</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b border-subtle last:border-0">
                  <td className="py-2 pr-3">
                    <span className="flex items-center gap-2">
                      <span className="font-medium text-secondary">{job.name}</span>
                      {!job.enabled && (
                        <Badge variant="neutral" size="sm">
                          {t("instance_dashboard.health.jobs.disabled")}
                        </Badge>
                      )}
                      {job.is_stale && (
                        <Badge variant="warning" size="sm">
                          {t("instance_dashboard.health.jobs.overdue")}
                        </Badge>
                      )}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-tertiary">{job.schedule_display}</td>
                  <td className="py-2 text-right tabular-nums text-tertiary">
                    {job.seconds_since_last_run === null
                      ? t("instance_dashboard.health.jobs.never")
                      : t("instance_dashboard.health.jobs.ago", {
                          duration: formatDuration(job.seconds_since_last_run),
                        })}
                  </td>
                  <td className="py-2 text-right tabular-nums text-tertiary">{job.total_run_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PanelCard>
  );
};
