/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";

type Props = {
  label: string;
  status: string | null;
  syncedAt: string | null;
};

/**
 * One line of sync health. Issues and the wiki each get their own, because they
 * run independently and a single shared line meant the slower of the two silently
 * spoke for both.
 */
export const GithubSyncStatus = ({ label, status, syncedAt }: Props) => {
  const { t } = useTranslation();
  const failed = !!status && status.startsWith("error");

  return (
    <p className="text-11 text-tertiary mt-0.5">
      <span className="font-medium">{label}</span>
      {": "}
      {syncedAt ? (
        <>
          {new Date(syncedAt).toLocaleString()}
          {status ? <span className={failed ? "text-danger" : undefined}> — {status}</span> : null}
        </>
      ) : (
        t("project_settings.github_sync.never_synced")
      )}
    </p>
  );
};
