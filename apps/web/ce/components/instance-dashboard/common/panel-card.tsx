/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Card, ECardSpacing, ECardVariant } from "@plane/propel/card";
import { Loader } from "@plane/ui";

type Props = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  isLoading?: boolean;
  error?: unknown;
  children: ReactNode;
  className?: string;
};

/**
 * A dashboard panel with its own loading and error state.
 *
 * Each panel owns its request, so one failing endpoint dims one card instead
 * of blanking the page — the client-side counterpart to the per-probe
 * isolation on the server.
 */
export const PanelCard = ({ title, subtitle, actions, isLoading, error, children, className }: Props) => {
  const { t } = useTranslation();

  return (
    <Card variant={ECardVariant.WITHOUT_SHADOW} spacing={ECardSpacing.LG} className={className}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-primary">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-tertiary">{subtitle}</p>}
        </div>
        {actions}
      </div>

      <div className="mt-4">
        {isLoading ? (
          <Loader className="space-y-2">
            <Loader.Item height="20px" />
            <Loader.Item height="20px" width="80%" />
            <Loader.Item height="20px" width="60%" />
          </Loader>
        ) : error ? (
          <p className="text-sm text-danger-primary">{t("instance_dashboard.panel_error")}</p>
        ) : (
          children
        )}
      </div>
    </Card>
  );
};
