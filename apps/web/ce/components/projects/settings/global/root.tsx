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

export const GlobalSettingsRoot = observer(function GlobalSettingsRoot(props: Props) {
  const { workspaceSlug, projectId, isAdmin } = props;
  const { t } = useTranslation();
  const { currentProjectDetails, updateProject } = useProject();

  const handleToggle = async () => {
    if (!currentProjectDetails) return;
    try {
      await updateProject(workspaceSlug, projectId, {
        is_global: !currentProjectDetails.is_global,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("toast.success"),
        message: t("global_project.settings.updated_success"),
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("global_project.settings.updated_error"),
      });
    }
  };

  const handleChange = (value: boolean) => {
    if (value !== currentProjectDetails?.is_global) {
      void handleToggle();
    }
  };

  return (
    <div className={`w-full ${!isAdmin ? "opacity-60" : ""}`}>
      <div className="flex items-center justify-between gap-4 py-4 border-b border-subtle">
        <div>
          <h4 className="text-sm font-medium text-primary">{t("global_project.settings.label")}</h4>
          <p className="text-sm text-secondary mt-1">{t("global_project.settings.description")}</p>
        </div>
        <ToggleSwitch
          value={currentProjectDetails?.is_global ?? false}
          onChange={handleChange}
          disabled={!isAdmin}
          size="sm"
        />
      </div>
    </div>
  );
});
