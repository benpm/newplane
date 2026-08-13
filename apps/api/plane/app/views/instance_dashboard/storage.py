# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Storage usage: database size, file-asset rollups and object-store scans."""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.app.views.instance_dashboard.caching import (
    resilient_cache_response,
    safe_cache_add,
    safe_cache_delete,
    safe_cache_get,
    safe_cache_set,
)
from plane.utils.instance_storage import (
    asset_storage_rollup,
    postgres_sizes,
    scan_bucket,
)

BUCKET_SCAN_CACHE_KEY = "instance_dashboard:bucket_scan"
BUCKET_SCAN_LOCK_KEY = "instance_dashboard:bucket_scan:lock"
BUCKET_SCAN_TTL_SECONDS = 6 * 60 * 60
BUCKET_SCAN_STALE_AFTER_SECONDS = 6 * 60 * 60
BUCKET_SCAN_LOCK_TTL_SECONDS = 60


def cached_bucket_scan():
    """The last bucket scan, aged.

    Read straight from the cache rather than through a response decorator:
    that path no-ops under DEBUG (so local dev would rescan on every request)
    and cannot be written by the POST handler that produces the value.
    """
    cached = safe_cache_get(BUCKET_SCAN_CACHE_KEY)
    if not cached:
        return {"status": "never"}

    scanned_at = cached.get("scanned_at")
    if scanned_at:
        age = (timezone.now() - scanned_at).total_seconds()
        cached = {**cached, "status": ("stale" if age > BUCKET_SCAN_STALE_AFTER_SECONDS else "fresh")}
    return cached


class InstanceStorageEndpoint(InstanceDashboardBaseView):
    """Database size, largest tables, and file-asset byte rollups."""

    @resilient_cache_response(300)
    def get(self, request):
        return Response(
            {
                "postgres": postgres_sizes(),
                "assets": asset_storage_rollup(),
                "bucket_scan": cached_bucket_scan(),
            }
        )


class InstanceBucketScanEndpoint(InstanceDashboardBaseView):
    """Read or trigger a walk of the object-storage bucket.

    Kept off the storage endpoint deliberately: a scan is the only unbounded
    operation on the dashboard, so it happens when an admin asks for it and
    never as a side effect of loading a page.
    """

    def get(self, request):
        return Response(cached_bucket_scan())

    def post(self, request):
        # Atomic set-if-absent; two admins clicking at once means one scan.
        # With the cache down this returns True and the scan proceeds unlocked
        # — a duplicate scan is a far smaller problem than a dead button.
        if not safe_cache_add(BUCKET_SCAN_LOCK_KEY, "1", BUCKET_SCAN_LOCK_TTL_SECONDS):
            return Response({"status": "running"}, status=status.HTTP_202_ACCEPTED)

        try:
            result = scan_bucket()
            result["scanned_at"] = timezone.now()
            safe_cache_set(BUCKET_SCAN_CACHE_KEY, result, BUCKET_SCAN_TTL_SECONDS)
            return Response(result)
        except Exception as exc:
            return Response({"status": "error", "error": str(exc)[:200]})
        finally:
            safe_cache_delete(BUCKET_SCAN_LOCK_KEY)
