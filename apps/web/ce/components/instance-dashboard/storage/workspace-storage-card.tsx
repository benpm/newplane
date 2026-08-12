/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import type { TInstanceStorage } from "@plane/types";
// local
import { formatBytes, formatNumber } from "../common/format";
import { PanelCard } from "../common/panel-card";

type Props = { byWorkspace: TInstanceStorage["assets"]["by_workspace"] };

/** Which workspaces account for the file storage. */
export const WorkspaceStorageCard = ({ byWorkspace }: Props) => {
  const { t } = useTranslation();
  const largest = byWorkspace[0]?.best_effort_bytes ?? 0;

  return (
    <PanelCard
      title={t("instance_dashboard.storage.by_workspace")}
      subtitle={t("instance_dashboard.storage.by_workspace_subtitle")}
    >
      {byWorkspace.length === 0 ? (
        <p className="text-sm text-tertiary">{t("instance_dashboard.storage.no_assets")}</p>
      ) : (
        <div className="space-y-3">
          {byWorkspace.map((workspace) => (
            <div key={workspace.workspace_id}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium text-secondary">{workspace.workspace_name}</span>
                <span className="shrink-0 tabular-nums text-tertiary">
                  {formatBytes(workspace.best_effort_bytes)} · {formatNumber(workspace.count)}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-layer-2">
                <div
                  className="h-full rounded-full bg-brand-primary"
                  style={{ width: `${largest > 0 ? (workspace.best_effort_bytes / largest) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelCard>
  );
};
