# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Caching that survives the cache being down.

The stock ``cache_response`` decorator calls ``cache.get()`` unguarded, and the
cache backend is Redis. For a dashboard that reports on Redis, that is exactly
backwards: the moment the page matters most is the moment the wrapper raises,
before the view ever runs, and the probe that would have said "redis: down"
never executes.

Everything here degrades instead. A dead cache means uncached responses, not
failed ones.
"""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response

from plane.utils.cache import generate_cache_key


def safe_cache_get(key, default=None):
    try:
        value = cache.get(key)
        return default if value is None else value
    except Exception:
        return default


def safe_cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
        return True
    except Exception:
        return False


def safe_cache_add(key, value, timeout):
    """Atomic set-if-absent. Returns False when the key exists.

    Also returns **True** when the cache is unreachable: the caller uses this
    to acquire a lock, and refusing to work because the lock cannot be taken
    would turn a degraded cache into a broken feature.
    """
    try:
        return cache.add(key, value, timeout)
    except Exception:
        return True


def safe_cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        pass


def resilient_cache_response(timeout=60, path=None, user=False):
    """``cache_response``, minus the hard dependency on the cache being up."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(instance, request, *args, **kwargs):
            auth_header = None if request.user.is_anonymous else str(request.user.id) if user else None
            key = generate_cache_key(path if path is not None else request.get_full_path(), auth_header)

            cached = safe_cache_get(key)
            if cached is not None:
                return Response(cached["data"], status=cached["status"])

            response = view_func(instance, request, *args, **kwargs)
            if response.status_code == 200 and not settings.DEBUG:
                safe_cache_set(key, {"data": response.data, "status": response.status_code}, timeout)
            return response

        return _wrapped_view

    return decorator
