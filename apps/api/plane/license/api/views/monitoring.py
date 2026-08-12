# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework.response import Response

# Module imports
from plane.db.models.notification import EmailNotificationLog
from plane.license.api.serializers.monitoring import (
    EmailNotificationLogSerializer,
)
from plane.license.api.views.base import BaseAPIView
from plane.utils.cache import cache_response
from plane.utils.instance_probes import list_scheduled_jobs, probe_celery_workers


class EmailLogMonitoringEndpoint(BaseAPIView):
    """Paginated issue email notification logs for admin monitoring."""

    def get(self, request):
        queryset = EmailNotificationLog.objects.select_related(
            "receiver", "triggered_by"
        ).order_by("-created_at")

        # Apply optional filters
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        entity_name = request.query_params.get("entity_name")

        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        if entity_name:
            queryset = queryset.filter(entity_name=entity_name)

        return self.paginate(
            request=request,
            queryset=queryset,
            on_results=lambda results: EmailNotificationLogSerializer(
                results, many=True
            ).data,
            default_per_page=50,
            max_per_page=100,
        )


class ScheduledJobMonitoringEndpoint(BaseAPIView):
    """List all periodic tasks for admin monitoring (read-only)."""

    def get(self, request):
        # Shared with the instance dashboard's beat probe, which needs the
        # same rows to work out whether beat is still firing.
        return Response({"results": list_scheduled_jobs()}, status=200)


class WorkerHealthMonitoringEndpoint(BaseAPIView):
    """Live Celery worker stats via Inspect API, cached 30s."""

    @cache_response(30, user=False)
    def get(self, request):
        probe = probe_celery_workers()
        details = probe["details"]
        response = {
            "workers": details.get("workers", []),
            "summary": {
                "total_workers": details.get("total_workers", 0),
                "total_active_tasks": details.get("total_active_tasks", 0),
            },
        }
        if probe["error"]:
            response["error"] = "Could not reach Celery workers"
        return Response(response)
