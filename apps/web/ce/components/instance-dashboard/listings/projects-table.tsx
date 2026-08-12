/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardProject } from "@plane/types";
// local
import { formatNumber } from "../common/format";
import { SWR_KEY } from "../constants";
import { ListingShell } from "./listing-shell";
import { useListing } from "./use-listing";

const service = new InstanceDashboardService();

/** Every project across every workspace. */
export const ProjectsTable = () => {
  const { t } = useTranslation();
  const listing = useListing<TDashboardProject>(SWR_KEY.PROJECTS, (params) => service.fetchProjects(params));

  return (
    <ListingShell
      search={listing.search}
      onSearchChange={listing.setSearch}
      placeholder={t("instance_dashboard.listings.search_projects")}
      totalCount={listing.totalCount}
      isLoading={listing.isLoading}
      error={listing.error}
      isEmpty={listing.rows.length === 0}
      hasNext={listing.hasNext}
      hasPrev={listing.hasPrev}
      onNext={listing.goNext}
      onPrev={listing.goPrev}
    >
      <table className="w-full min-w-[46rem] text-sm">
        <thead>
          <tr className="border-b border-subtle text-left text-xs text-tertiary">
            <th className="pb-2 font-medium">{t("instance_dashboard.listings.name")}</th>
            <th className="pb-2 font-medium">{t("instance_dashboard.listings.workspace")}</th>
            <th className="pb-2 font-medium">{t("instance_dashboard.listings.lead")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.members")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.counts.work_items")}</th>
            <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.created")}</th>
          </tr>
        </thead>
        <tbody>
          {listing.rows.map((project) => (
            <tr key={project.id} className="border-b border-subtle last:border-0">
              <td className="py-2 pr-3">
                <span className="flex items-center gap-2">
                  <a
                    href={`/${project.workspace_slug}/projects/${project.id}/issues`}
                    className="font-medium text-secondary hover:text-primary"
                  >
                    {project.name}
                  </a>
                  <span className="text-xs text-tertiary">{project.identifier}</span>
                  {project.is_global && (
                    <Badge variant="brand" size="sm">
                      {t("instance_dashboard.listings.global")}
                    </Badge>
                  )}
                  {project.is_archived && (
                    <Badge variant="neutral" size="sm">
                      {t("instance_dashboard.listings.archived")}
                    </Badge>
                  )}
                </span>
              </td>
              <td className="py-2 pr-3 text-tertiary">{project.workspace_name}</td>
              <td className="py-2 pr-3 text-tertiary">{project.lead ?? "—"}</td>
              <td className="py-2 text-right tabular-nums text-tertiary">{formatNumber(project.member_count)}</td>
              <td className="py-2 text-right tabular-nums text-tertiary">{formatNumber(project.issue_count)}</td>
              <td className="py-2 text-right text-tertiary">{new Date(project.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ListingShell>
  );
};
