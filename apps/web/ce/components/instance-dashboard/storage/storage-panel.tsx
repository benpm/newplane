/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { InstanceDashboardService } from "@plane/services";
import { Loader } from "@plane/ui";
// local
import { SWR_KEY } from "../constants";
import { ObjectStorageCard } from "./object-storage-card";
import { PostgresCard } from "./postgres-card";
import { WorkspaceStorageCard } from "./workspace-storage-card";

const service = new InstanceDashboardService();

/** Database and object-storage usage. */
export const StoragePanel = () => {
  const { t } = useTranslation();
  const { data, isLoading, error, mutate } = useSWR(SWR_KEY.STORAGE, () => service.fetchStorage());

  if (isLoading) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="160px" />
        <Loader.Item height="320px" />
      </Loader>
    );
  }

  if (error || !data) {
    return <p className="text-sm text-danger-primary">{t("instance_dashboard.panel_error")}</p>;
  }

  return (
    <div className="space-y-4">
      <ObjectStorageCard storage={data} onScanned={() => void mutate()} />
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <PostgresCard postgres={data.postgres} />
        </div>
        <WorkspaceStorageCard byWorkspace={data.assets.by_workspace} />
      </div>
    </div>
  );
};
