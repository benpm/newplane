/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
// components
import { InstanceDashboardGate } from "@/plane-web/components/instance-dashboard";
// lib
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";

/**
 * Shell for the instance dashboard.
 *
 * Modelled on the profile-settings layout rather than the workspace layouts:
 * this page sits outside any workspace, so it brings its own frame instead of
 * AppHeader, whose sidebar toggle would be a dead control here.
 *
 * The admin gate lives in the layout so panels never mount — and never fire
 * requests that can only 403 — for a user who is not an instance admin.
 */
export default function InstanceDashboardLayout() {
  return (
    <AuthenticationWrapper>
      <div className="relative flex size-full overflow-hidden bg-canvas p-2">
        <main className="relative flex flex-col size-full overflow-hidden bg-surface-1 rounded-lg border border-subtle">
          <div className="size-full overflow-hidden">
            <InstanceDashboardGate>
              <Outlet />
            </InstanceDashboardGate>
          </div>
        </main>
      </div>
    </AuthenticationWrapper>
  );
}
