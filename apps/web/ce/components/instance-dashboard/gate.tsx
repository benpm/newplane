/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
// services
import { UserService } from "@/services/user.service";

const userService = new UserService();

/**
 * Restricts the instance dashboard to instance admins.
 *
 * The SWR key is shared verbatim with the four other places in the app that
 * ask this question, so the answer is deduped rather than refetched.
 *
 * A refused user is shown a plain "not authorised" state rather than being
 * redirected: a visible 403 can be reasoned about, whereas a redirect from a
 * URL someone was given reads as a broken link.
 */
export const InstanceDashboardGate = ({ children }: { children: ReactNode }) => {
  const { t } = useTranslation();
  const { data, isLoading, error } = useSWR("INSTANCE_ADMIN_STATUS", () =>
    userService.currentUserInstanceAdminStatus()
  );

  if (isLoading) {
    return (
      <div className="grid size-full place-items-center">
        <LogoSpinner />
      </div>
    );
  }

  if (error || !data?.is_instance_admin) {
    return (
      <div className="grid size-full place-items-center p-8">
        <EmptyStateDetailed
          title={t("instance_dashboard.access_denied.title")}
          description={t("instance_dashboard.access_denied.description")}
          assetKey="settings"
          assetClassName="size-40"
        />
      </div>
    );
  }

  return <>{children}</>;
};
