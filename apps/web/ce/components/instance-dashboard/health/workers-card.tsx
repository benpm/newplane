/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import type { TInstanceHealth } from "@plane/types";
// local
import { PanelCard } from "../common/panel-card";
import { StatusPill } from "../common/status-pill";

type Props = { health: TInstanceHealth | undefined; isLoading: boolean; error: unknown };

/** Celery workers and the broker queues they drain. */
export const WorkersCard = ({ health, isLoading, error }: Props) => {
  const { t } = useTranslation();
  const workers = health?.services.celery_workers;
  const queues = health?.services.rabbitmq.details.queues ?? [];

  return (
    <PanelCard
      title={t("instance_dashboard.health.workers.title")}
      subtitle={t("instance_dashboard.health.workers.subtitle")}
      isLoading={isLoading}
      error={error}
      actions={workers && <StatusPill status={workers.status} />}
    >
      {workers?.error && <p className="mb-3 text-xs text-danger-primary">{workers.error}</p>}

      {(workers?.details.workers ?? []).length === 0 ? (
        <p className="text-sm text-tertiary">{t("instance_dashboard.health.workers.none")}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-subtle text-left text-xs text-tertiary">
              <th className="pb-2 font-medium">{t("instance_dashboard.health.workers.name")}</th>
              <th className="pb-2 font-medium">{t("instance_dashboard.health.workers.pool")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.health.workers.active")}</th>
            </tr>
          </thead>
          <tbody>
            {(workers?.details.workers ?? []).map((worker) => (
              <tr key={worker.name} className="border-b border-subtle last:border-0">
                <td className="py-2 font-medium text-secondary">{worker.name}</td>
                <td className="py-2 text-tertiary">{worker.pool_info ?? "—"}</td>
                <td className="py-2 text-right tabular-nums text-secondary">{worker.active_tasks}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {queues.length > 0 && (
        <div className="mt-4 border-t border-subtle pt-3">
          <p className="mb-2 text-xs font-medium text-tertiary">{t("instance_dashboard.health.workers.queues")}</p>
          {queues.map((queue) => (
            <div key={queue.name} className="flex items-baseline justify-between text-xs">
              <span className="text-secondary">{queue.name}</span>
              <span className="tabular-nums text-tertiary">
                {queue.note
                  ? queue.note
                  : t("instance_dashboard.health.workers.queue_depth", {
                      messages: queue.messages ?? 0,
                      consumers: queue.consumers ?? 0,
                    })}
              </span>
            </div>
          ))}
        </div>
      )}
    </PanelCard>
  );
};
