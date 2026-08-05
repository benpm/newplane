/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/propel/input";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { ToggleSwitch } from "@plane/ui";
// services
import { CEProjectGithubSyncService } from "@/plane-web/services/project-github-sync.service";

const githubSyncService = new CEProjectGithubSyncService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
};

export const GithubSyncSettingsRoot = observer(function GithubSyncSettingsRoot(props: Props) {
  const { workspaceSlug, projectId, isAdmin } = props;
  const { t } = useTranslation();
  const [repositoryInput, setRepositoryInput] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  const {
    data: githubSync,
    isLoading,
    mutate,
  } = useSWR(
    workspaceSlug && projectId ? `PROJECT_GITHUB_SYNC_${projectId}` : null,
    workspaceSlug && projectId ? () => githubSyncService.fetch(workspaceSlug, projectId) : null
  );

  const run = async (operation: () => Promise<unknown>, successKey: string) => {
    setIsBusy(true);
    try {
      await operation();
      await mutate();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("toast.success"), message: t(successKey) });
    } catch (error) {
      console.error(error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("project_settings.github_sync.request_failed"),
      });
    } finally {
      setIsBusy(false);
    }
  };

  if (isLoading) return null;

  return (
    <div className="w-full border-t border-subtle pt-6 mt-6">
      <h3 className="text-base font-medium text-primary">{t("project_settings.github_sync.title")}</h3>
      <p className="text-13 text-secondary mt-1">{t("project_settings.github_sync.description")}</p>

      {!githubSync ? (
        <div className="mt-4 flex items-center gap-2">
          <Input
            value={repositoryInput}
            onChange={(e) => setRepositoryInput(e.target.value)}
            placeholder={t("project_settings.github_sync.repository_placeholder")}
            className="w-64"
            disabled={!isAdmin}
          />
          <Button
            variant="primary"
            size="sm"
            loading={isBusy}
            disabled={!isAdmin || !repositoryInput.trim()}
            onClick={() =>
              void run(
                () => githubSyncService.connect(workspaceSlug, projectId, { repository: repositoryInput.trim() }),
                "project_settings.github_sync.connected"
              )
            }
          >
            {t("project_settings.github_sync.connect")}
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-13 font-medium text-primary">{githubSync.repository}</p>
              <p className="text-11 text-tertiary mt-0.5">
                {githubSync.last_synced_at
                  ? `${t("project_settings.github_sync.last_synced")}: ${new Date(githubSync.last_synced_at).toLocaleString()} — ${githubSync.last_sync_status ?? ""}`
                  : t("project_settings.github_sync.never_synced")}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                loading={isBusy}
                disabled={!isAdmin}
                onClick={() =>
                  void run(
                    () => githubSyncService.syncNow(workspaceSlug, projectId),
                    "project_settings.github_sync.sync_started"
                  )
                }
              >
                {t("project_settings.github_sync.sync_now")}
              </Button>
              <Button
                variant="error-outline"
                size="sm"
                loading={isBusy}
                disabled={!isAdmin}
                onClick={() =>
                  void run(
                    () => githubSyncService.disconnect(workspaceSlug, projectId),
                    "project_settings.github_sync.disconnected"
                  )
                }
              >
                {t("project_settings.github_sync.disconnect")}
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-13 font-medium text-primary">{t("project_settings.github_sync.issue_sync_label")}</p>
              <p className="text-11 text-tertiary mt-0.5">{t("project_settings.github_sync.issue_sync_description")}</p>
            </div>
            <ToggleSwitch
              value={githubSync.is_issue_sync_enabled}
              onChange={() =>
                void run(
                  () =>
                    githubSyncService.update(workspaceSlug, projectId, {
                      is_issue_sync_enabled: !githubSync.is_issue_sync_enabled,
                    }),
                  "project_settings.github_sync.updated"
                )
              }
              disabled={!isAdmin}
              size="sm"
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-13 font-medium text-primary">{t("project_settings.github_sync.wiki_sync_label")}</p>
              <p className="text-11 text-tertiary mt-0.5">{t("project_settings.github_sync.wiki_sync_description")}</p>
            </div>
            <ToggleSwitch
              value={githubSync.is_wiki_sync_enabled}
              onChange={() =>
                void run(
                  () =>
                    githubSyncService.update(workspaceSlug, projectId, {
                      is_wiki_sync_enabled: !githubSync.is_wiki_sync_enabled,
                    }),
                  "project_settings.github_sync.updated"
                )
              }
              disabled={!isAdmin}
              size="sm"
            />
          </div>
        </div>
      )}
    </div>
  );
});
