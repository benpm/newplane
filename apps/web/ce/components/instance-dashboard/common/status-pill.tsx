/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import type { TServiceStatus } from "@plane/types";
// local
import { STATUS_VARIANT } from "../constants";

type Props = {
  status: TServiceStatus;
  latencyMs?: number | null;
};

/** Service status as a coloured badge, with round-trip latency when known. */
export const StatusPill = ({ status, latencyMs }: Props) => {
  const { t } = useTranslation();

  return (
    <span className="inline-flex items-center gap-2">
      <Badge variant={STATUS_VARIANT[status]} size="sm">
        {t(`instance_dashboard.status.${status}`)}
      </Badge>
      {latencyMs !== null && latencyMs !== undefined && (
        <span className="text-xs text-tertiary tabular-nums">{latencyMs} ms</span>
      )}
    </span>
  );
};
