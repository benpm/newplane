/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { Card, ECardSpacing, ECardVariant } from "@plane/propel/card";
import type { TServiceProbe } from "@plane/types";
// local
import { StatusPill } from "../common/status-pill";

type Props = {
  label: string;
  probe: TServiceProbe | undefined;
  rows?: { label: string; value: React.ReactNode }[];
};

/** One dependency: its status, its latency, and a few key readings. */
export const ServiceCard = ({ label, probe, rows = [] }: Props) => {
  if (!probe) return null;

  return (
    <Card variant={ECardVariant.WITHOUT_SHADOW} spacing={ECardSpacing.SM} className="gap-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-medium text-primary">{label}</h4>
        <StatusPill status={probe.status} latencyMs={probe.latency_ms} />
      </div>

      {probe.error && <p className="text-xs text-danger-primary break-words">{probe.error}</p>}

      {rows.length > 0 && (
        <dl className="space-y-1">
          {rows.map((row) => (
            <div key={row.label} className="flex items-baseline justify-between gap-3">
              <dt className="text-xs text-tertiary">{row.label}</dt>
              <dd className="text-xs font-medium text-secondary tabular-nums">{row.value ?? "—"}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
};
