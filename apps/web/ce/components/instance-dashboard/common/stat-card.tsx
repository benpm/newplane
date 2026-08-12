/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
// plane imports
import { Card, ECardSpacing, ECardVariant } from "@plane/propel/card";

type StatCardProps = {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
};

/** One headline number with a label and optional qualifier beneath it. */
export const StatCard = ({ label, value, sub }: StatCardProps) => (
  <Card variant={ECardVariant.WITHOUT_SHADOW} spacing={ECardSpacing.SM} className="gap-1">
    <p className="text-xs font-medium text-tertiary">{label}</p>
    <p className="text-2xl font-semibold text-primary tabular-nums">{value}</p>
    {sub && <p className="text-xs text-tertiary">{sub}</p>}
  </Card>
);

/** Responsive grid of StatCards. */
export const StatGrid = ({ children }: { children: ReactNode }) => (
  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{children}</div>
);
