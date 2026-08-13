# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .health import InstanceHealthEndpoint
from .invites import (
    InstanceDashboardInviteDetailEndpoint,
    InstanceDashboardInviteEndpoint,
)
from .jobs import InstanceDashboardScheduledJobsEndpoint
from .listings import (
    InstanceDashboardProjectListEndpoint,
    InstanceDashboardUserListEndpoint,
    InstanceDashboardWorkspaceListEndpoint,
)
from .overview import InstanceOverviewEndpoint
from .storage import InstanceBucketScanEndpoint, InstanceStorageEndpoint
from .users import InstanceDashboardUserDetailEndpoint

__all__ = [
    "InstanceBucketScanEndpoint",
    "InstanceDashboardInviteDetailEndpoint",
    "InstanceDashboardInviteEndpoint",
    "InstanceDashboardProjectListEndpoint",
    "InstanceDashboardScheduledJobsEndpoint",
    "InstanceDashboardUserDetailEndpoint",
    "InstanceDashboardUserListEndpoint",
    "InstanceDashboardWorkspaceListEndpoint",
    "InstanceHealthEndpoint",
    "InstanceOverviewEndpoint",
    "InstanceStorageEndpoint",
]
