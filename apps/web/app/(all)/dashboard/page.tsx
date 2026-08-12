/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { PageHead } from "@/components/core/page-title";
import { InstanceDashboardRoot } from "@/plane-web/components/instance-dashboard";

export default function InstanceDashboardPage() {
  const { t } = useTranslation();

  return (
    <>
      <PageHead title={t("instance_dashboard.title")} />
      <InstanceDashboardRoot />
    </>
  );
}
