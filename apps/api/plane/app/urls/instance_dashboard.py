# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Routes for the instance dashboard.

WARNING: no path here may contain the substring ``instances``.

``plane.authentication.middleware.session.SessionMiddleware`` chooses which
session cookie to read by testing ``"instances" in request.path``. These
endpoints are served to apps/web, which holds the *app* session cookie, so a
path matching that test would make every request anonymous and every response
a 403. ``test_instance_dashboard_permissions.py`` enforces this.
"""

from django.urls import path

from plane.app.views.instance_dashboard import (
    InstanceBucketScanEndpoint,
    InstanceDashboardProjectListEndpoint,
    InstanceDashboardScheduledJobsEndpoint,
    InstanceDashboardUserListEndpoint,
    InstanceDashboardWorkspaceListEndpoint,
    InstanceHealthEndpoint,
    InstanceOverviewEndpoint,
    InstanceStorageEndpoint,
)

urlpatterns = [
    path(
        "instance-dashboard/health/",
        InstanceHealthEndpoint.as_view(),
        name="instance-dashboard-health",
    ),
    path(
        "instance-dashboard/overview/",
        InstanceOverviewEndpoint.as_view(),
        name="instance-dashboard-overview",
    ),
    path(
        "instance-dashboard/storage/",
        InstanceStorageEndpoint.as_view(),
        name="instance-dashboard-storage",
    ),
    path(
        "instance-dashboard/storage/bucket-scan/",
        InstanceBucketScanEndpoint.as_view(),
        name="instance-dashboard-bucket-scan",
    ),
    path(
        "instance-dashboard/workspaces/",
        InstanceDashboardWorkspaceListEndpoint.as_view(),
        name="instance-dashboard-workspaces",
    ),
    path(
        "instance-dashboard/users/",
        InstanceDashboardUserListEndpoint.as_view(),
        name="instance-dashboard-users",
    ),
    path(
        "instance-dashboard/projects/",
        InstanceDashboardProjectListEndpoint.as_view(),
        name="instance-dashboard-projects",
    ),
    path(
        "instance-dashboard/scheduled-jobs/",
        InstanceDashboardScheduledJobsEndpoint.as_view(),
        name="instance-dashboard-scheduled-jobs",
    ),
]
