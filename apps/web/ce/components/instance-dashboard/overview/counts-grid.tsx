/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import type { TInstanceOverview } from "@plane/types";
// local
import { formatNumber } from "../common/format";
import { StatCard, StatGrid } from "../common/stat-card";

/** Headline counts for every major entity in the instance. */
export const CountsGrid = ({ overview }: { overview: TInstanceOverview }) => {
  const { t } = useTranslation();

  return (
    <StatGrid>
      <StatCard label={t("instance_dashboard.counts.workspaces")} value={formatNumber(overview.workspaces)} />
      <StatCard
        label={t("instance_dashboard.counts.users")}
        value={formatNumber(overview.users.total)}
        sub={t("instance_dashboard.counts.users_active", { count: overview.users.active })}
      />
      <StatCard
        label={t("instance_dashboard.counts.projects")}
        value={formatNumber(overview.projects.total)}
        sub={t("instance_dashboard.counts.projects_global", { count: overview.projects.global })}
      />
      <StatCard
        label={t("instance_dashboard.counts.work_items")}
        value={formatNumber(overview.work_items.total)}
        sub={t("instance_dashboard.counts.created_last_7d", { count: overview.work_items.created_last_7d })}
      />
      <StatCard label={t("instance_dashboard.counts.cycles")} value={formatNumber(overview.cycles)} />
      <StatCard label={t("instance_dashboard.counts.modules")} value={formatNumber(overview.modules)} />
      <StatCard label={t("instance_dashboard.counts.pages")} value={formatNumber(overview.pages)} />
      <StatCard label={t("instance_dashboard.counts.comments")} value={formatNumber(overview.comments)} />
      <StatCard label={t("instance_dashboard.counts.views")} value={formatNumber(overview.views)} />
      <StatCard label={t("instance_dashboard.counts.labels")} value={formatNumber(overview.labels)} />
      <StatCard label={t("instance_dashboard.counts.attachments")} value={formatNumber(overview.attachments)} />
      <StatCard
        label={t("instance_dashboard.counts.departments")}
        value={formatNumber(overview.departments)}
        sub={t("instance_dashboard.counts.staff", { count: overview.staff })}
      />
    </StatGrid>
  );
};
