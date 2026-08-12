/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
// local
import { PanelCard } from "../common/panel-card";

/**
 * Instance identity and which sign-in methods are enabled.
 *
 * Read from the instance store rather than a dashboard endpoint: the app
 * already loads `GET /api/instances/` on boot, so this costs no request.
 */
export const InstanceInfoCard = observer(() => {
  const { t } = useTranslation();
  const { instance, config } = useInstance();

  const providers: { key: string; enabled: boolean | undefined }[] = [
    { key: "email_password", enabled: config?.is_email_password_enabled },
    { key: "magic_login", enabled: config?.is_magic_login_enabled },
    { key: "google", enabled: config?.is_google_enabled },
    { key: "github", enabled: config?.is_github_enabled },
    { key: "gitlab", enabled: config?.is_gitlab_enabled },
    { key: "gitea", enabled: config?.is_gitea_enabled },
    { key: "ldap", enabled: config?.is_ldap_enabled },
    { key: "swing_sso", enabled: config?.is_swing_sso_enabled },
  ];
  const enabled = providers.filter((provider) => provider.enabled);

  return (
    <PanelCard title={t("instance_dashboard.overview.instance")}>
      <dl className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-xs text-tertiary">{t("instance_dashboard.runtime.instance")}</dt>
          <dd className="text-xs font-medium text-secondary">{instance?.instance_name ?? "—"}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-xs text-tertiary">{t("instance_dashboard.runtime.version")}</dt>
          <dd className="text-xs font-medium text-secondary">{instance?.current_version ?? "—"}</dd>
        </div>
        {/* Edition lives on the Health tab's runtime card, which reads the
            dashboard's own endpoint — the shared IInstance type omits it. */}
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-xs text-tertiary">{t("instance_dashboard.runtime.latest_version")}</dt>
          <dd className="text-xs font-medium text-secondary">{instance?.latest_version ?? "—"}</dd>
        </div>
      </dl>

      <div className="mt-4 border-t border-subtle pt-3">
        <p className="mb-2 text-xs font-medium text-tertiary">{t("instance_dashboard.overview.auth_providers")}</p>
        {enabled.length === 0 ? (
          <p className="text-xs text-tertiary">{t("instance_dashboard.overview.no_auth_providers")}</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {enabled.map((provider) => (
              <Badge key={provider.key} variant="neutral" size="sm">
                {t(`instance_dashboard.auth_provider.${provider.key}`)}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </PanelCard>
  );
});
