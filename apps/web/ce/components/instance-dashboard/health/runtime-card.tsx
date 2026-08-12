/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import type { TInstanceHealth } from "@plane/types";
// local
import { PanelCard } from "../common/panel-card";

type Props = { health: TInstanceHealth | undefined; isLoading: boolean; error: unknown };

/** Versions, deployment mode and mail configuration. */
export const RuntimeCard = ({ health, isLoading, error }: Props) => {
  const { t } = useTranslation();
  const runtime = health?.runtime;
  const smtp = runtime?.smtp;

  const rows: { label: string; value: React.ReactNode }[] = [
    { label: t("instance_dashboard.runtime.instance"), value: runtime?.instance_name ?? "—" },
    { label: t("instance_dashboard.runtime.version"), value: runtime?.current_version ?? "—" },
    { label: t("instance_dashboard.runtime.latest_version"), value: runtime?.latest_version ?? "—" },
    { label: t("instance_dashboard.runtime.edition"), value: runtime?.edition ?? "—" },
    { label: t("instance_dashboard.runtime.python"), value: runtime?.python_version ?? "—" },
    { label: t("instance_dashboard.runtime.django"), value: runtime?.django_version ?? "—" },
    {
      label: t("instance_dashboard.runtime.smtp"),
      value: smtp?.configured
        ? `${smtp.host ?? ""}${smtp.port ? `:${smtp.port}` : ""}`
        : t("instance_dashboard.runtime.smtp_unconfigured"),
    },
  ];

  return (
    <PanelCard
      title={t("instance_dashboard.runtime.title")}
      isLoading={isLoading}
      error={error}
      actions={
        runtime?.debug ? (
          <Badge variant="warning" size="sm">
            {t("instance_dashboard.runtime.debug_on")}
          </Badge>
        ) : undefined
      }
    >
      <dl className="space-y-1.5">
        {rows.map((row) => (
          <div key={row.label} className="flex items-baseline justify-between gap-3">
            <dt className="text-xs text-tertiary">{row.label}</dt>
            <dd className="text-xs font-medium text-secondary">{row.value}</dd>
          </div>
        ))}
      </dl>
    </PanelCard>
  );
};
