/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardWorkspace } from "@plane/types";
// local
import { formatNumber } from "../common/format";
import { SWR_KEY } from "../constants";
import { ListingShell } from "./listing-shell";
import { useListing } from "./use-listing";

const service = new InstanceDashboardService();

/** Every workspace on the instance. */
export const WorkspacesTable = () => {
  const { t } = useTranslation();
  const listing = useListing<TDashboardWorkspace>(SWR_KEY.WORKSPACES, (params) => service.fetchWorkspaces(params));

  return (
    <ListingShell
      search={listing.search}
      onSearchChange={listing.setSearch}
      placeholder={t("instance_dashboard.listings.search_workspaces")}
      totalCount={listing.totalCount}
      isLoading={listing.isLoading}
      error={listing.error}
      isEmpty={listing.rows.length === 0}
      hasNext={listing.hasNext}
      hasPrev={listing.hasPrev}
      onNext={listing.goNext}
      onPrev={listing.goPrev}
    >
      <table className="w-full min-w-[42rem] text-sm">
        <thead>
          <tr className="border-b border-subtle text-left text-xs text-tertiary">
            <th className="pb-2 font-medium">{t("instance_dashboard.listings.name")}</th>
            <th className="pb-2 font-medium">{t("instance_dashboard.listings.owner")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.counts.projects")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.members")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.counts.work_items")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.created")}</th>
          </tr>
        </thead>
        <tbody>
          {listing.rows.map((workspace) => (
            <tr key={workspace.id} className="border-b border-subtle last:border-0">
              <td className="py-2 pr-3">
                <a href={`/${workspace.slug}`} className="font-medium text-secondary hover:text-primary">
                  {workspace.name}
                </a>
                <span className="ml-2 text-xs text-tertiary">/{workspace.slug}</span>
              </td>
              <td className="py-2 pr-3 text-tertiary">{workspace.owner ?? "—"}</td>
              <td className="py-2 text-right tabular-nums text-tertiary">{formatNumber(workspace.total_projects)}</td>
              <td className="py-2 text-right tabular-nums text-tertiary">{formatNumber(workspace.total_members)}</td>
              <td className="py-2 text-right tabular-nums text-tertiary">{formatNumber(workspace.total_issues)}</td>
              <td className="py-2 text-right text-tertiary">{new Date(workspace.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ListingShell>
  );
};
