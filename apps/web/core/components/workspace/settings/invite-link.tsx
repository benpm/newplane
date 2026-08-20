/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { EUserPermissions } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TUserPermissions } from "@plane/types";
import { CustomSelect } from "@plane/ui";
import { copyTextToClipboard } from "@plane/utils";
// services
import { WorkspaceService } from "@/services/workspace.service";

const workspaceService = new WorkspaceService();

const ROLE_OPTIONS: { value: TUserPermissions; labelKey: string }[] = [
  { value: EUserPermissions.GUEST, labelKey: "workspace_settings.settings.members.invite_link.role_guest" },
  { value: EUserPermissions.MEMBER, labelKey: "workspace_settings.settings.members.invite_link.role_member" },
  { value: EUserPermissions.ADMIN, labelKey: "workspace_settings.settings.members.invite_link.role_admin" },
];

type Props = { workspaceSlug: string };

export const WorkspaceInviteLinkSection = observer(function WorkspaceInviteLinkSection({ workspaceSlug }: Props) {
  const { t } = useTranslation();
  const [role, setRole] = useState<TUserPermissions>(EUserPermissions.MEMBER);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data, mutate } = useSWR(
    workspaceSlug ? `WORKSPACE_INVITE_LINK_${workspaceSlug}` : null,
    workspaceSlug ? () => workspaceService.getWorkspaceInviteLink(workspaceSlug) : null
  );

  const inviteLink = data && "token" in data ? data : undefined;
  const absoluteLink = inviteLink ? `${window.location.origin}${inviteLink.invite_link}` : "";

  const handleGenerate = async () => {
    setIsSubmitting(true);
    try {
      const created = await workspaceService.createWorkspaceInviteLink(workspaceSlug, role);
      await mutate(created, false);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workspace_settings.settings.members.invite_link.generated") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("workspace_settings.settings.members.invite_link.generate_failed") });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRevoke = async () => {
    setIsSubmitting(true);
    try {
      await workspaceService.revokeWorkspaceInviteLink(workspaceSlug);
      await mutate({ invite_link: null }, false);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workspace_settings.settings.members.invite_link.revoked") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("workspace_settings.settings.members.invite_link.revoke_failed") });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = () => {
    void copyTextToClipboard(absoluteLink).then(() =>
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workspace_settings.settings.members.invite_link.copied") })
    );
  };

  return (
    <div className="mb-6 rounded-md border border-subtle bg-surface-1 p-4">
      <h5 className="text-13 font-medium text-primary">{t("workspace_settings.settings.members.invite_link.title")}</h5>
      <p className="mt-1 text-11 text-tertiary">{t("workspace_settings.settings.members.invite_link.description")}</p>

      {inviteLink ? (
        <div className="mt-4 flex flex-col gap-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              readOnly
              value={absoluteLink}
              onFocus={(e) => e.target.select()}
              className="w-full rounded-md border border-subtle bg-layer-2 px-3 py-2 text-13 text-secondary outline-none"
            />
            <div className="flex flex-shrink-0 items-center gap-2">
              <Button variant="secondary" size="sm" onClick={handleCopy}>
                {t("copy_link")}
              </Button>
              <Button variant="error-outline" size="sm" onClick={() => void handleRevoke()} disabled={isSubmitting}>
                {t("workspace_settings.settings.members.invite_link.revoke")}
              </Button>
            </div>
          </div>
          <span className="text-11 text-tertiary">
            {t("workspace_settings.settings.members.invite_link.usage", { count: inviteLink.uses })}
          </span>
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
          <CustomSelect
            value={role}
            label={<span className="text-13">{t(ROLE_OPTIONS.find((o) => o.value === role)?.labelKey ?? "")}</span>}
            onChange={(value: TUserPermissions) => setRole(value)}
            buttonClassName="border-subtle bg-layer-2"
            input
          >
            {ROLE_OPTIONS.map((option) => (
              <CustomSelect.Option key={option.value} value={option.value}>
                {t(option.labelKey)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
          <Button variant="primary" size="sm" onClick={() => void handleGenerate()} disabled={isSubmitting}>
            {t("workspace_settings.settings.members.invite_link.generate")}
          </Button>
        </div>
      )}
    </div>
  );
});
