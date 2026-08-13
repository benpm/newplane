# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Failure isolation for the health endpoint.

The dashboard exists to be looked at when something is broken, so a broken
dependency must render as a red panel rather than a 500. These tests break
each probe in turn and assert the page still answers.
"""

import uuid

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import User
from plane.license.models import Instance, InstanceAdmin
from plane.utils import instance_probes

PROBES = [
    ("redis", "probe_redis"),
    ("rabbitmq", "probe_rabbitmq"),
    ("object_storage", "probe_object_storage"),
    ("postgres", "probe_postgres"),
]


@pytest.fixture(autouse=True)
def clear_response_cache():
    """The health endpoint caches for 15s, keyed by path and not by user.

    That is deliberate in production — the probes are the expensive part and
    every admin sees the same instance. In tests it means one case's response
    would be served to the next, so each starts from cold.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_client(db):
    instance = Instance.objects.create(
        instance_name="Test Instance",
        is_setup_done=True,
        last_checked_at=timezone.now(),
    )
    user = User.objects.create(
        email=f"probe-admin-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
        display_name="probe-admin",
    )
    InstanceAdmin.objects.create(instance=instance, user=user, role=20, is_super_admin=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.parametrize("service,probe_name", PROBES)
def test_one_dead_dependency_does_not_break_the_page(admin_client, monkeypatch, service, probe_name):
    """A probe that raises becomes an `unknown` panel, not a 500."""

    def explode():
        raise ConnectionError("connection refused")

    monkeypatch.setattr(instance_probes, probe_name, explode)
    # health.py imported the probes by name, so patch there too.
    from plane.app.views.instance_dashboard import health

    monkeypatch.setattr(health, probe_name, explode)

    response = admin_client.get(reverse("instance-dashboard-health"))

    assert response.status_code == 200
    assert response.data["services"][service]["status"] in ("unknown", "down")
    assert response.data["overall"] in ("unknown", "down", "degraded")


def test_broker_down_short_circuits_worker_inspection(admin_client, monkeypatch):
    """Worker inspection broadcasts over the broker.

    With the broker down that call can only time out, so it is skipped rather
    than spending six seconds to rediscover the same failure.
    """
    from plane.app.views.instance_dashboard import health

    monkeypatch.setattr(
        health,
        "probe_rabbitmq",
        lambda: {"status": "down", "latency_ms": None, "error": "refused", "details": {}},
    )

    def should_not_run():
        raise AssertionError("workers were inspected despite the broker being down")

    monkeypatch.setattr(health, "probe_celery_workers", should_not_run)

    response = admin_client.get(reverse("instance-dashboard-health"))

    assert response.status_code == 200
    assert response.data["services"]["celery_workers"]["status"] == "unknown"


def test_probe_errors_never_leak_credentials(admin_client, monkeypatch, settings):
    """Connection errors quote the URL that failed, and those carry passwords.

    kombu's failures read like `amqp://user:password@host:5672/`, so the raw
    exception text would publish the broker password to anyone who can load
    the dashboard.
    """
    password = "sup3r-s3cret-broker-pw"
    settings.RABBITMQ_PASSWORD = password

    def explode():
        raise ConnectionError(f"failed to connect to amqp://plane:{password}@plane-mq:5672/")

    monkeypatch.setattr(instance_probes, "Connection", explode, raising=False)

    from plane.app.views.instance_dashboard import health

    monkeypatch.setattr(health, "probe_rabbitmq", instance_probes.probe_rabbitmq)
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", f"amqp://plane:{password}@nonexistent-broker:5672/")

    response = admin_client.get(reverse("instance-dashboard-health"))

    assert response.status_code == 200
    assert password not in str(response.data), "the broker password reached the HTTP response"


def test_sanitize_strips_secrets_directly(settings):
    """The sanitiser is the single chokepoint, so test it on its own too."""
    settings.RABBITMQ_PASSWORD = "broker-password-value"
    scrubbed = instance_probes._sanitize(ConnectionError("amqp://plane:broker-password-value@mq:5672/ refused"))
    assert "broker-password-value" not in scrubbed
    assert "***" in scrubbed


def test_worst_status_folds_to_the_most_severe():
    assert instance_probes.worst_status(["ok", "ok"]) == "ok"
    assert instance_probes.worst_status(["ok", "degraded"]) == "degraded"
    assert instance_probes.worst_status(["ok", "degraded", "down"]) == "down"
    assert instance_probes.worst_status(["ok", "unknown"]) == "unknown"
    assert instance_probes.worst_status([]) == "unknown"


@pytest.mark.parametrize(
    "url_name",
    [
        "instance-dashboard-health",
        "instance-dashboard-overview",
        "instance-dashboard-storage",
        "instance-dashboard-scheduled-jobs",
    ],
)
def test_a_dead_cache_does_not_break_the_dashboard(admin_client, monkeypatch, url_name):
    """The cache backend is Redis, and Redis is one of the things being reported.

    The stock `cache_response` decorator calls `cache.get()` unguarded, so with
    Redis down it raised *before* the view ran — the health page 500'd at
    exactly the moment it was needed, and the probe that would have said
    "redis: down" never executed. `resilient_cache_response` degrades to
    uncached instead. This test is the guard on that.
    """
    from django.core.cache import cache

    def explode(*args, **kwargs):
        raise ConnectionError("Error -2 connecting to redis:6379. Name does not resolve.")

    monkeypatch.setattr(cache, "get", explode)
    monkeypatch.setattr(cache, "set", explode)

    response = admin_client.get(reverse(url_name))

    assert response.status_code == 200, f"{url_name} failed with the cache down"


def test_scheduled_jobs_are_empty_without_the_beat_scheduler(admin_client):
    """django_celery_beat is not installed under the test settings.

    An instance not running beat should report no scheduled jobs, not crash.
    """
    response = admin_client.get(reverse("instance-dashboard-scheduled-jobs"))
    assert response.status_code == 200
    assert response.data["results"] == []
