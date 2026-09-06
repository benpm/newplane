/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// assets
import { useTranslation } from "@plane/i18n";
import packageJson from "package.json";

export function PlaneVersionNumber() {
  const { t } = useTranslation();
  const commitHash = process.env.VITE_GIT_COMMIT_HASH;
  return (
    <span>
      {t("version")}: v{packageJson.version}
      {commitHash ? ` (${commitHash})` : ""}
    </span>
  );
}
