/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { ToggleSwitch } from "@plane/ui";
import { useProject } from "@/hooks/store/use-project";

type Props = {
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
};

export const AutoAddUsersSettingsRoot = observer(function AutoAddUsersSettingsRoot(props: Props) {
  const { workspaceSlug, projectId, isAdmin } = props;
  const { t } = useTranslation();
  const { currentProjectDetails, updateProject } = useProject();

  const handleToggle = async () => {
    if (!currentProjectDetails) return;
    try {
      await updateProject(workspaceSlug, projectId, {
        auto_add_new_users: !currentProjectDetails.auto_add_new_users,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("toast.success"),
        message: t("project_settings.auto_add_new_users.updated_success"),
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("project_settings.auto_add_new_users.updated_error"),
      });
    }
  };

  const handleChange = (value: boolean) => {
    if (value !== currentProjectDetails?.auto_add_new_users) {
      void handleToggle();
    }
  };

  return (
    <div className={`w-full ${!isAdmin ? "opacity-60" : ""}`}>
      <div className="flex items-center justify-between gap-4 py-4 border-b border-subtle">
        <div>
          <h4 className="text-13 font-medium text-primary">{t("project_settings.auto_add_new_users.label")}</h4>
          <p className="text-13 text-secondary mt-1">{t("project_settings.auto_add_new_users.description")}</p>
        </div>
        <ToggleSwitch
          value={currentProjectDetails?.auto_add_new_users ?? false}
          onChange={handleChange}
          disabled={!isAdmin}
          size="sm"
        />
      </div>
    </div>
  );
});
