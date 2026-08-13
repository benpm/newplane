/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Copy, Trash2 } from "lucide-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardWorkspace } from "@plane/types";
import { Loader } from "@plane/ui";
// local
import { INVITE_ROLES, SWR_KEY } from "../constants";
import { InviteForm } from "./invite-form";

const service = new InstanceDashboardService();

const roleLabelKey = (role: number) =>
  INVITE_ROLES.find((option) => option.value === role)?.labelKey ?? "instance_dashboard.invites.role_member";

/** Outstanding invites, and the form that creates them. */
export const InvitesTable = () => {
  const { t } = useTranslation();
  const [revoking, setRevoking] = useState<string | null>(null);

  const { data, isLoading, error, mutate } = useSWR(SWR_KEY.INVITES, () => service.fetchInvites());
  // The workspace picker needs the full list; per_page covers any realistic instance.
  const { data: workspaceData } = useSWR([SWR_KEY.WORKSPACES, "for-invites"], () =>
    service.fetchWorkspaces({ per_page: "100" })
  );

  const invites = data?.results ?? [];
  const workspaces: TDashboardWorkspace[] = workspaceData?.results ?? [];

  const copyLink = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("instance_dashboard.invites.copied") });
    } catch {
      // Clipboard access needs a secure context; show the link so it can be
      // selected by hand rather than failing silently.
      setToast({
        type: TOAST_TYPE.INFO,
        title: t("instance_dashboard.invites.copy_failed"),
        message: link,
      });
    }
  };

  const revoke = async (id: string) => {
    setRevoking(id);
    try {
      await service.revokeInvite(id);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("instance_dashboard.invites.revoked") });
      void mutate();
    } catch (revokeError) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("instance_dashboard.invites.revoke_failed"),
        message: (revokeError as { error?: string })?.error,
      });
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div className="space-y-4">
      <InviteForm
        workspaces={workspaces}
        onCreated={(link) => {
          void mutate();
          void copyLink(link);
        }}
      />

      {isLoading ? (
        <Loader className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <Loader.Item key={index} height="40px" />
          ))}
        </Loader>
      ) : error ? (
        <p className="text-sm text-danger-primary">{t("instance_dashboard.panel_error")}</p>
      ) : invites.length === 0 ? (
        <p className="py-8 text-center text-sm text-tertiary">{t("instance_dashboard.invites.none")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[42rem] text-sm">
            <thead>
              <tr className="border-b border-subtle text-left text-xs text-tertiary">
                <th className="pb-2 font-medium">{t("instance_dashboard.invites.invitee")}</th>
                <th className="pb-2 font-medium">{t("instance_dashboard.listings.workspace")}</th>
                <th className="pb-2 font-medium">{t("instance_dashboard.invites.role")}</th>
                <th className="pb-2 text-right font-medium">{t("instance_dashboard.listings.created")}</th>
                <th className="pb-2 text-right font-medium">{t("instance_dashboard.invites.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {invites.map((invite) => (
                <tr key={invite.id} className="border-b border-subtle last:border-0">
                  <td className="py-2 pr-3">
                    <span className="font-medium text-secondary">{invite.display_name || invite.email}</span>
                    {invite.display_name && <span className="ml-2 text-xs text-tertiary">{invite.email}</span>}
                  </td>
                  <td className="py-2 pr-3 text-tertiary">{invite.workspace_name}</td>
                  <td className="py-2 pr-3">
                    <Badge variant="neutral" size="sm">
                      {t(roleLabelKey(invite.role))}
                    </Badge>
                  </td>
                  <td className="py-2 text-right text-tertiary">{new Date(invite.created_at).toLocaleDateString()}</td>
                  <td className="py-2 text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => void copyLink(invite.link)}
                        title={t("instance_dashboard.invites.copy_link")}
                        className="rounded p-1.5 text-tertiary hover:bg-layer-1-hover hover:text-primary"
                      >
                        <Copy className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void revoke(invite.id)}
                        disabled={revoking === invite.id}
                        title={t("instance_dashboard.invites.revoke")}
                        className="rounded p-1.5 text-tertiary hover:bg-layer-1-hover hover:text-danger-primary disabled:opacity-50"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
