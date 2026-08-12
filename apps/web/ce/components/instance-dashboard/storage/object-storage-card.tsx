/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Badge } from "@plane/propel/badge";
import { Button } from "@plane/propel/button";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { InstanceDashboardService } from "@plane/services";
import type { TInstanceStorage } from "@plane/types";
// local
import { formatBytes, formatNumber } from "../common/format";
import { PanelCard } from "../common/panel-card";

const service = new InstanceDashboardService();

type Props = { storage: TInstanceStorage; onScanned: () => void };

/**
 * Object-storage usage.
 *
 * Three numbers are shown side by side rather than reconciled into one:
 * declared bytes are a client-supplied reservation, measured bytes come from
 * real ContentLength readings that only some assets carry, and the scan is
 * ground truth. Averaging them would produce a confident wrong answer.
 */
export const ObjectStorageCard = ({ storage, onScanned }: Props) => {
  const { t } = useTranslation();
  const [isScanning, setIsScanning] = useState(false);
  const { assets, bucket_scan: scan } = storage;

  const handleScan = async () => {
    setIsScanning(true);
    try {
      await service.runBucketScan();
      onScanned();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("instance_dashboard.storage.scan_complete") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("instance_dashboard.storage.scan_failed") });
    } finally {
      setIsScanning(false);
    }
  };

  const coverage = assets.measured_coverage;
  const hasScan = scan.status === "fresh" || scan.status === "stale";

  return (
    <PanelCard
      title={t("instance_dashboard.storage.object_storage")}
      subtitle={t("instance_dashboard.storage.object_storage_subtitle")}
      actions={
        <Button variant="secondary" size="sm" onClick={() => void handleScan()} loading={isScanning}>
          {t("instance_dashboard.storage.run_scan")}
        </Button>
      }
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Figure
          label={t("instance_dashboard.storage.scanned")}
          value={hasScan ? formatBytes(scan.total_bytes) : "—"}
          hint={
            hasScan
              ? t("instance_dashboard.storage.objects", { count: scan.object_count ?? 0 })
              : t("instance_dashboard.storage.never_scanned")
          }
          badge={
            scan.status === "stale" ? (
              <Badge variant="warning" size="sm">
                {t("instance_dashboard.storage.stale")}
              </Badge>
            ) : scan.truncated ? (
              <Badge variant="warning" size="sm">
                {t("instance_dashboard.storage.partial")}
              </Badge>
            ) : undefined
          }
        />
        <Figure
          label={t("instance_dashboard.storage.measured")}
          value={formatBytes(assets.measured_bytes)}
          hint={
            coverage === null
              ? t("instance_dashboard.storage.no_assets")
              : t("instance_dashboard.storage.coverage", { percent: Math.round(coverage * 100) })
          }
        />
        <Figure
          label={t("instance_dashboard.storage.declared")}
          value={formatBytes(assets.declared_bytes)}
          hint={t("instance_dashboard.storage.declared_hint")}
        />
        <Figure
          label={t("instance_dashboard.storage.reclaimable")}
          value={formatBytes(assets.soft_deleted_bytes + assets.pending_bytes)}
          hint={t("instance_dashboard.storage.reclaimable_hint", {
            deleted: assets.soft_deleted_count,
            pending: assets.pending_count,
          })}
        />
      </div>

      {hasScan && (
        <p className="mt-3 text-xs text-tertiary">
          {t("instance_dashboard.storage.unreconciled", {
            bytes: formatBytes((scan.total_bytes ?? 0) - assets.measured_bytes),
          })}
        </p>
      )}

      {assets.by_entity_type.length > 0 && (
        <div className="mt-4 border-t border-subtle pt-3">
          <p className="mb-2 text-xs font-medium text-tertiary">{t("instance_dashboard.storage.by_entity_type")}</p>
          {assets.by_entity_type.map((entity) => (
            <div key={entity.entity_type} className="flex items-baseline justify-between text-xs">
              <span className="text-secondary">{entity.entity_type}</span>
              <span className="tabular-nums text-tertiary">
                {formatBytes(entity.best_effort_bytes)} · {formatNumber(entity.count)}
              </span>
            </div>
          ))}
        </div>
      )}
    </PanelCard>
  );
};

const Figure = ({
  label,
  value,
  hint,
  badge,
}: {
  label: string;
  value: string;
  hint: string;
  badge?: React.ReactNode;
}) => (
  <div className="rounded-lg border border-subtle p-3">
    <div className="flex items-center gap-2">
      <p className="text-xs font-medium text-tertiary">{label}</p>
      {badge}
    </div>
    <p className="mt-1 text-xl font-semibold text-primary tabular-nums">{value}</p>
    <p className="mt-0.5 text-xs text-tertiary">{hint}</p>
  </div>
);
