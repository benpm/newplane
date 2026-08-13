/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { PencilLine, UserMinus, UserPlus } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardUser } from "@plane/types";
// local
import { SWR_KEY } from "../constants";
import { DeactivateUserModal } from "./deactivate-user-modal";
import { ListingShell } from "./listing-shell";
import { RenameUserModal } from "./rename-user-modal";
import { useListing } from "./use-listing";

const service = new InstanceDashboardService();

/** Every user account on the instance, with rename and suspend actions. */
export const UsersTable = () => {
  const { t } = useTranslation();
  const listing = useListing<TDashboardUser>(SWR_KEY.USERS, (params) => service.fetchUsers(params));
  const [renaming, setRenaming] = useState<TDashboardUser | null>(null);
  const [suspending, setSuspending] = useState<TDashboardUser | null>(null);

  return (
    <>
      <ListingShell
        search={listing.search}
        onSearchChange={listing.setSearch}
        placeholder={t("instance_dashboard.listings.search_users")}
        totalCount={listing.totalCount}
        isLoading={listing.isLoading}
        error={listing.error}
        isEmpty={listing.rows.length === 0}
        hasNext={listing.hasNext}
        hasPrev={listing.hasPrev}
        onNext={listing.goNext}
        onPrev={listing.goPrev}
      >
        <table className="w-full min-w-[48rem] text-sm">
          <thead>
            <tr className="border-b border-subtle text-left text-xs text-tertiary">
              <th className="pb-2 font-medium">{t("instance_dashboard.listings.name")}</th>
              <th className="pb-2 font-medium">{t("instance_dashboard.listings.email")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.counts.workspaces")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.joined")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.last_login")}</th>
              <th className="pb-2 text-right font-medium">{t("instance_dashboard.invites.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {listing.rows.map((user) => (
              <tr key={user.id} className="border-b border-subtle last:border-0">
                <td className="py-2 pr-3">
                  <span className="flex items-center gap-2">
                    <span className="font-medium text-secondary">{user.display_name || "—"}</span>
                    {user.is_instance_admin && (
                      <Badge variant="brand" size="sm">
                        {t("instance_dashboard.listings.admin")}
                      </Badge>
                    )}
                    {!user.is_active && (
                      <Badge variant="neutral" size="sm">
                        {t("instance_dashboard.listings.inactive")}
                      </Badge>
                    )}
                  </span>
                </td>
                <td className="py-2 pr-3 text-tertiary">{user.email}</td>
                <td className="py-2 text-right tabular-nums text-tertiary">{user.workspace_count}</td>
                <td className="py-2 text-right text-tertiary">{new Date(user.date_joined).toLocaleDateString()}</td>
                <td className="py-2 text-right text-tertiary">
                  {user.last_login ? new Date(user.last_login).toLocaleDateString() : "—"}
                </td>
                <td className="py-2 text-right">
                  <div className="flex justify-end gap-1">
                    <button
                      type="button"
                      onClick={() => setRenaming(user)}
                      title={t("instance_dashboard.users.rename_action")}
                      className="rounded p-1.5 text-tertiary hover:bg-layer-1-hover hover:text-primary"
                    >
                      <PencilLine className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setSuspending(user)}
                      title={
                        user.is_active
                          ? t("instance_dashboard.users.deactivate_action")
                          : t("instance_dashboard.users.reactivate_action")
                      }
                      className="rounded p-1.5 text-tertiary hover:bg-layer-1-hover hover:text-primary"
                    >
                      {user.is_active ? <UserMinus className="size-3.5" /> : <UserPlus className="size-3.5" />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ListingShell>

      <RenameUserModal user={renaming} onClose={() => setRenaming(null)} onRenamed={listing.refresh} />
      <DeactivateUserModal user={suspending} onClose={() => setSuspending(null)} onChanged={listing.refresh} />
    </>
  );
};
