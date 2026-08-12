# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Instance-wide entity counts."""

from rest_framework.response import Response

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.license.utils.instance_counts import instance_counts
from plane.utils.cache import cache_response


class InstanceOverviewEndpoint(InstanceDashboardBaseView):
    """Counts of every major entity across the whole instance."""

    @cache_response(60, user=False)
    def get(self, request):
        return Response(instance_counts())
