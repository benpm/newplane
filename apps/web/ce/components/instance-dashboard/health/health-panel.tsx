/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { InstanceDashboardService } from "@plane/services";
// local
import { formatBytes, formatDuration, formatNumber } from "../common/format";
import { StatusPill } from "../common/status-pill";
import { HEALTH_REFRESH_INTERVAL_MS, SWR_KEY } from "../constants";
import { RuntimeCard } from "./runtime-card";
import { ScheduledJobsCard } from "./scheduled-jobs-card";
import { ServiceCard } from "./service-card";
import { WorkersCard } from "./workers-card";

const service = new InstanceDashboardService();

/** Live status of every service the instance depends on. */
export const HealthPanel = () => {
  const { t } = useTranslation();
  const { data, isLoading, error } = useSWR(SWR_KEY.HEALTH, () => service.fetchHealth(), {
    refreshInterval: HEALTH_REFRESH_INTERVAL_MS,
  });

  const services = data?.services;
  const postgres = services?.postgres.details;
  const redis = services?.redis.details;
  const beat = services?.celery_beat.details;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm text-tertiary">{t("instance_dashboard.health.overall")}</span>
        {data && <StatusPill status={data.overall} />}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ServiceCard
          label={t("instance_dashboard.health.postgres")}
          probe={services?.postgres}
          rows={[
            { label: t("instance_dashboard.health.version"), value: postgres?.server_version },
            { label: t("instance_dashboard.health.size"), value: formatBytes(postgres?.database_size_bytes) },
            {
              label: t("instance_dashboard.health.connections"),
              value: `${formatNumber(postgres?.active_connections)} / ${formatNumber(postgres?.max_connections)}`,
            },
          ]}
        />
        <ServiceCard
          label={t("instance_dashboard.health.redis")}
          probe={services?.redis}
          rows={[
            { label: t("instance_dashboard.health.version"), value: redis?.version },
            { label: t("instance_dashboard.health.memory"), value: formatBytes(redis?.used_memory_bytes) },
            { label: t("instance_dashboard.health.keys"), value: formatNumber(redis?.keys) },
          ]}
        />
        <ServiceCard
          label={t("instance_dashboard.health.rabbitmq")}
          probe={services?.rabbitmq}
          rows={[
            { label: t("instance_dashboard.health.host"), value: services?.rabbitmq.details.host },
            { label: t("instance_dashboard.health.vhost"), value: services?.rabbitmq.details.vhost },
          ]}
        />
        <ServiceCard
          label={t("instance_dashboard.health.object_storage")}
          probe={services?.object_storage}
          rows={[
            { label: t("instance_dashboard.health.backend"), value: services?.object_storage.details.backend },
            { label: t("instance_dashboard.health.bucket"), value: services?.object_storage.details.bucket },
          ]}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <WorkersCard health={data} isLoading={isLoading} error={error} />
        <div className="grid gap-3">
          <ServiceCard
            label={t("instance_dashboard.health.beat")}
            probe={services?.celery_beat}
            rows={[
              { label: t("instance_dashboard.health.enabled_tasks"), value: formatNumber(beat?.enabled_task_count) },
              {
                label: t("instance_dashboard.health.last_beat"),
                value: formatDuration(beat?.seconds_since_last_run),
              },
              { label: t("instance_dashboard.health.overdue_tasks"), value: (beat?.stale_tasks ?? []).length },
            ]}
          />
          <RuntimeCard health={data} isLoading={isLoading} error={error} />
        </div>
      </div>

      <ScheduledJobsCard />
    </div>
  );
};
