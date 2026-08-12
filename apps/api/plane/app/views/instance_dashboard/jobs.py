# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Celery beat schedule, with staleness."""

from rest_framework.response import Response

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.utils.cache import cache_response
from plane.utils.instance_probes import list_scheduled_jobs


class InstanceDashboardScheduledJobsEndpoint(InstanceDashboardBaseView):
    """Every periodic task, when it last ran, and whether it is overdue."""

    @cache_response(30, user=False)
    def get(self, request):
        return Response({"results": list_scheduled_jobs()})
