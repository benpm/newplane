# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Service health for the instance dashboard."""

import django
import sys
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.license.models import Instance
from plane.app.views.instance_dashboard.caching import resilient_cache_response
from plane.utils.instance_probes import (
    DOWN,
    UNKNOWN,
    probe_celery_beat,
    probe_celery_workers,
    probe_object_storage,
    probe_postgres,
    probe_rabbitmq,
    probe_redis,
    smtp_settings,
    worst_status,
)

# Wall-clock ceiling for any one backgrounded probe. Each probe already sets
# its own client timeouts; this is the backstop for a client that ignores them.
_PROBE_TIMEOUT_SECONDS = 6


class InstanceHealthEndpoint(InstanceDashboardBaseView):
    """Live status of every service this instance depends on.

    Always answers 200 when the caller is authorised: a dependency being down
    is the *content* of this response, not an error in producing it.
    """

    @resilient_cache_response(15)
    def get(self, request):
        # Postgres stays on the request thread. Django's connections are
        # thread-local, so probing it from a pool worker would open one that
        # nothing ever closes.
        services = {"postgres": self._guard(probe_postgres)}

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                "redis": pool.submit(self._guard, probe_redis),
                "rabbitmq": pool.submit(self._guard, probe_rabbitmq),
                "object_storage": pool.submit(self._guard, probe_object_storage),
            }
            for name, future in futures.items():
                try:
                    services[name] = future.result(timeout=_PROBE_TIMEOUT_SECONDS)
                except Exception as exc:
                    services[name] = {
                        "status": UNKNOWN,
                        "latency_ms": None,
                        "error": str(exc)[:200],
                        "details": {},
                    }

        # Worker inspection broadcasts over the broker and waits for replies.
        # With the broker down that is six seconds spent to learn what we
        # already know, so skip it and say so.
        if services["rabbitmq"]["status"] == DOWN:
            services["celery_workers"] = {
                "status": UNKNOWN,
                "latency_ms": None,
                "error": "Broker unreachable — workers cannot be inspected",
                "details": {"workers": [], "total_workers": 0, "total_active_tasks": 0},
            }
        else:
            services["celery_workers"] = self._guard(probe_celery_workers)

        services["celery_beat"] = self._guard(probe_celery_beat)

        return Response(
            {
                "checked_at": timezone.now(),
                "overall": worst_status([service["status"] for service in services.values()]),
                "services": services,
                "runtime": self._runtime(),
            }
        )

    @staticmethod
    def _guard(probe):
        """Run a probe, converting any escapee into an `unknown` result.

        The probes promise not to raise. This is what happens when one breaks
        that promise: a single degraded panel rather than a 500 for the page.
        """
        try:
            return probe()
        except Exception as exc:
            return {"status": UNKNOWN, "latency_ms": None, "error": str(exc)[:200], "details": {}}

    @staticmethod
    def _runtime():
        instance = Instance.objects.first()
        return {
            "instance_id": instance.instance_id if instance else None,
            "instance_name": instance.instance_name if instance else None,
            # Also on GET /api/instances/, but that response is cached for two
            # hours — this one is fresh within 15 seconds.
            "current_version": instance.current_version if instance else None,
            "latest_version": instance.latest_version if instance else None,
            "edition": instance.edition if instance else None,
            "is_setup_done": instance.is_setup_done if instance else False,
            "debug": settings.DEBUG,
            "python_version": sys.version.split()[0],
            "django_version": django.get_version(),
            "smtp": smtp_settings(),
        }
