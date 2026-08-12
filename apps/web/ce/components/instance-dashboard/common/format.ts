/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const UNITS = ["B", "KB", "MB", "GB", "TB", "PB"];

/** Human-readable byte count. Binary units — this measures storage, not bandwidth. */
export const formatBytes = (bytes: number | null | undefined, fractionDigits = 1): string => {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "—";
  if (bytes === 0) return "0 B";

  const exponent = Math.min(Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)), UNITS.length - 1);
  const value = bytes / 1024 ** exponent;
  // Whole bytes never need a decimal point.
  return `${value.toFixed(exponent === 0 ? 0 : fractionDigits)} ${UNITS[exponent]}`;
};

export const formatNumber = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : value.toLocaleString();

/** Compact relative duration: "4m", "3h", "2d". */
export const formatDuration = (seconds: number | null | undefined): string => {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
};
