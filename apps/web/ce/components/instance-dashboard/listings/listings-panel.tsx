/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// local
import { ProjectsTable } from "./projects-table";
import { UsersTable } from "./users-table";
import { WorkspacesTable } from "./workspaces-table";

const SUB_TABS = ["workspaces", "projects", "users"] as const;
type TSubTab = (typeof SUB_TABS)[number];

/** Full inventories, one table at a time. */
export const ListingsPanel = () => {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TSubTab>("workspaces");

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-subtle">
        {SUB_TABS.map((subTab) => (
          <button
            key={subTab}
            type="button"
            onClick={() => setTab(subTab)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              tab === subTab
                ? "border-brand-primary text-primary"
                : "border-transparent text-tertiary hover:text-secondary"
            )}
          >
            {t(`instance_dashboard.counts.${subTab}`)}
          </button>
        ))}
      </div>

      {tab === "workspaces" && <WorkspacesTable />}
      {tab === "projects" && <ProjectsTable />}
      {tab === "users" && <UsersTable />}
    </div>
  );
};
