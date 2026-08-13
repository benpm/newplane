/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/propel/input";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { InstanceDashboardService } from "@plane/services";
import type { TDashboardWorkspace } from "@plane/types";
// local
import { INVITE_ROLES } from "../constants";

const service = new InstanceDashboardService();

type Props = { workspaces: TDashboardWorkspace[]; onCreated: (link: string) => void };

/** Create a named invite and hand back a link to share. No email is sent. */
export const InviteForm = ({ workspaces, onCreated }: Props) => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [role, setRole] = useState(15);
  const [isSaving, setIsSaving] = useState(false);

  const canSubmit = email.trim().length > 0 && workspaceId.length > 0;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setIsSaving(true);
    try {
      const invite = await service.createInvite({
        email: email.trim(),
        display_name: displayName.trim(),
        workspace_id: workspaceId,
        role,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: invite.reused ? t("instance_dashboard.invites.updated") : t("instance_dashboard.invites.created"),
        message: t("instance_dashboard.invites.link_ready"),
      });
      setEmail("");
      setDisplayName("");
      onCreated(invite.link);
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("instance_dashboard.invites.create_failed"),
        message: (error as { error?: string })?.error,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-subtle p-4">
      <h4 className="text-sm font-semibold text-primary">{t("instance_dashboard.invites.new")}</h4>
      <p className="mt-0.5 text-xs text-tertiary">{t("instance_dashboard.invites.new_description")}</p>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label={t("instance_dashboard.invites.email")}>
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="person@example.com"
            className="w-full bg-layer-2"
          />
        </Field>
        <Field label={t("instance_dashboard.invites.display_name")}>
          <Input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={t("instance_dashboard.invites.display_name_placeholder")}
            className="w-full bg-layer-2"
          />
        </Field>
        <Field label={t("instance_dashboard.invites.workspace")}>
          <select
            value={workspaceId}
            onChange={(event) => setWorkspaceId(event.target.value)}
            className="w-full rounded border border-subtle bg-layer-2 px-2 py-1.5 text-sm text-primary"
          >
            <option value="">{t("instance_dashboard.invites.choose_workspace")}</option>
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("instance_dashboard.invites.role")}>
          <select
            value={role}
            onChange={(event) => setRole(Number(event.target.value))}
            className="w-full rounded border border-subtle bg-layer-2 px-2 py-1.5 text-sm text-primary"
          >
            {INVITE_ROLES.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.labelKey)}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="mt-3 flex justify-end">
        <Button
          variant="primary"
          size="sm"
          onClick={() => void handleSubmit()}
          loading={isSaving}
          disabled={!canSubmit}
        >
          {t("instance_dashboard.invites.generate")}
        </Button>
      </div>
    </div>
  );
};

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="space-y-1">
    <label className="block text-xs font-medium text-tertiary">{label}</label>
    {children}
  </div>
);
