# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Liveness probes for the services this instance depends on.

Every probe returns the same envelope and **never raises**::

    {"status": "ok"|"degraded"|"down"|"unknown",
     "latency_ms": float | None,
     "error": str | None,
     "details": {...}}

That uniformity is what lets the dashboard stay up when a dependency is not:
the caller renders whatever came back instead of returning a 500 because one
of six checks blew up.

Two rules every probe here obeys:

1. **Explicit timeouts.** The shared clients elsewhere in the codebase
   (``redis_instance()``, ``S3Storage``) set none, so a wedged dependency
   would hang the request for a botocore-default 60s or, for Redis, forever.
   Probes build their own short-timeout clients.
2. **No credentials in the output.** Broker and SMTP settings carry passwords;
   only host/port/vhost are ever returned, and exception text is truncated.
"""

import time
from urllib.parse import urlsplit

from django.conf import settings
from django.db import connection, transaction

OK = "ok"
DEGRADED = "degraded"
DOWN = "down"
UNKNOWN = "unknown"

# Worst-first, so `max(..., key=SEVERITY.index)` folds a set of statuses.
SEVERITY = [OK, DEGRADED, UNKNOWN, DOWN]

_ERROR_MAX_LEN = 200


def worst_status(statuses):
    """Fold service statuses into a single overall status."""
    return max(statuses, key=SEVERITY.index) if statuses else UNKNOWN


def _sanitize(exc):
    """Render an exception as short, credential-free text.

    Connection errors habitually embed the URL that failed, and those URLs
    carry passwords (``amqp://user:pass@host``). Strip anything that looks
    like userinfo before it reaches an HTTP response.
    """
    text = str(exc) or exc.__class__.__name__
    for secret in (
        settings.RABBITMQ_PASSWORD,
        settings.AWS_SECRET_ACCESS_KEY,
    ):
        if secret and len(secret) > 3:
            text = text.replace(secret, "***")
    return text[:_ERROR_MAX_LEN]


def _result(status, started_at=None, error=None, details=None):
    return {
        "status": status,
        "latency_ms": (round((time.monotonic() - started_at) * 1000, 2) if started_at is not None else None),
        "error": error,
        "details": details or {},
    }


def probe_postgres():
    """Ping Postgres and read server-level counters.

    Runs on the request thread: Django connections are thread-local, and a
    pooled worker thread would open one that Django never closes.
    """
    started = time.monotonic()
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # LOCAL, not a bare SET: with CONN_MAX_AGE the connection is
                # reused, and a session-level timeout would silently cap every
                # later query on it.
                cursor.execute("SET LOCAL statement_timeout = '3s'")
                cursor.execute("SELECT 1")
                cursor.execute("SHOW server_version")
                server_version = cursor.fetchone()[0]
                cursor.execute("SELECT pg_database_size(current_database()), current_database()")
                db_size, db_name = cursor.fetchone()
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                active_connections = cursor.fetchone()[0]
                cursor.execute("SHOW max_connections")
                max_connections = int(cursor.fetchone()[0])

        details = {
            "server_version": server_version,
            "database": db_name,
            "active_connections": active_connections,
            "max_connections": max_connections,
            "database_size_bytes": int(db_size),
        }
        # Saturating the connection pool is the failure that takes the whole
        # instance down, so surface it before it happens.
        status = DEGRADED if max_connections and active_connections > max_connections * 0.8 else OK
        return _result(status, started, details=details)
    except Exception as exc:
        return _result(DOWN, started, error=_sanitize(exc))


def _redis_client():
    """Build a probe-local Redis client with real socket timeouts."""
    import redis

    if settings.REDIS_SSL:
        url = urlsplit(settings.REDIS_URL)
        return redis.Redis(
            host=url.hostname,
            port=url.port,
            password=url.password,
            ssl=True,
            ssl_cert_reqs=None,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return redis.Redis.from_url(
        settings.REDIS_URL,
        db=0,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def probe_redis():
    """Ping Redis/Valkey and read memory + keyspace counters."""
    if not settings.REDIS_URL:
        return _result(UNKNOWN, error="REDIS_URL is not configured")

    started = time.monotonic()
    client = None
    try:
        client = _redis_client()
        client.ping()
        info = client.info()
        db_keys = client.dbsize()

        used_memory = int(info.get("used_memory", 0))
        max_memory = int(info.get("maxmemory", 0))
        details = {
            # Valkey reports itself through the same INFO field Redis uses.
            "server": info.get("server_name", "redis"),
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "used_memory_bytes": used_memory,
            "maxmemory_bytes": max_memory,
            "connected_clients": info.get("connected_clients"),
            "evicted_keys": info.get("evicted_keys"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "keys": db_keys,
        }
        status = DEGRADED if max_memory and used_memory > max_memory * 0.9 else OK
        return _result(status, started, details=details)
    except Exception as exc:
        return _result(DOWN, started, error=_sanitize(exc))
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _broker_target():
    """Host/port/vhost of the broker, with any password discarded."""
    parts = urlsplit(settings.CELERY_BROKER_URL)
    return {
        "host": parts.hostname or settings.RABBITMQ_HOST,
        "port": parts.port or settings.RABBITMQ_PORT,
        "vhost": (parts.path or "/").lstrip("/") or "/",
    }


def probe_rabbitmq(queues=("celery",)):
    """Connect to the broker and read queue depth for each named queue.

    Uses kombu (a hard Celery dependency, already installed) rather than the
    management HTTP API: no extra package, no reliance on the management
    plugin, and it works over the same AMQP port Celery already uses.
    """
    started = time.monotonic()
    details = _broker_target()
    try:
        from kombu import Connection

        with Connection(settings.CELERY_BROKER_URL, connect_timeout=3) as conn:
            conn.ensure_connection(max_retries=0, timeout=3)
            queue_info = []
            for queue_name in queues:
                # A passive declare against a missing queue raises a
                # channel-level 404 that *closes the channel*, so each queue
                # gets its own channel or one absent queue kills the rest.
                channel = conn.channel()
                try:
                    declared = channel.queue_declare(queue=queue_name, passive=True)
                    queue_info.append(
                        {
                            "name": queue_name,
                            "messages": declared.message_count,
                            "consumers": declared.consumer_count,
                        }
                    )
                except Exception:
                    queue_info.append(
                        {
                            "name": queue_name,
                            "messages": None,
                            "consumers": None,
                            "note": "queue not declared",
                        }
                    )
                finally:
                    try:
                        channel.close()
                    except Exception:
                        pass

        details["queues"] = queue_info
        # A queue with messages and nobody draining it means work is stranded.
        stalled = any(q.get("messages") and not q.get("consumers") for q in queue_info)
        return _result(DEGRADED if stalled else OK, started, details=details)
    except Exception as exc:
        return _result(DOWN, started, error=_sanitize(exc), details=details)


def probe_celery_workers():
    """Inspect live Celery workers.

    ``inspect`` broadcasts over the broker and waits for replies, so this is
    the slowest probe and it reports nothing useful when the broker is down —
    callers should skip it in that case rather than pay the timeout twice.
    """
    from plane.celery import app

    started = time.monotonic()
    try:
        inspector = app.control.inspect(timeout=3.0)
        active = inspector.active() or {}
        stats = inspector.stats() or {}
    except Exception as exc:
        return _result(
            DOWN,
            started,
            error=_sanitize(exc),
            details={"workers": [], "total_workers": 0, "total_active_tasks": 0},
        )

    workers = []
    total_active = 0
    for worker_name in sorted(set(list(active.keys()) + list(stats.keys()))):
        active_tasks = len(active.get(worker_name, []))
        total_active += active_tasks

        worker_stats = stats.get(worker_name, {})
        pool = worker_stats.get("pool", {})
        pool_impl = pool.get("implementation", "")
        pool_processes = len(pool.get("processes", []))
        clock = worker_stats.get("clock", None)

        workers.append(
            {
                "name": worker_name,
                "active_tasks": active_tasks,
                "uptime": f"{clock} ticks" if clock else None,
                "pool_info": (f"{pool_impl} ({pool_processes} procs)" if pool_impl else None),
            }
        )

    details = {
        "workers": workers,
        "total_workers": len(workers),
        "total_active_tasks": total_active,
    }
    return _result(OK if workers else DOWN, started, details=details)


# Period name -> seconds, for turning an IntervalSchedule into a duration.
_PERIOD_SECONDS = {
    "microseconds": 1e-6,
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
    "days": 86400,
}


def _expected_interval_seconds(task):
    """Best-effort period for a periodic task, in seconds.

    Crontabs are only bucketed — the point is staleness detection, not an
    exact next-run calculation, and croniter is not a dependency here.
    """
    if task.interval:
        return int(task.interval.every * _PERIOD_SECONDS.get(task.interval.period, 60))
    if task.crontab:
        crontab = task.crontab
        if crontab.day_of_month != "*" or crontab.month_of_year != "*":
            return 31 * 86400
        if crontab.day_of_week != "*":
            return 7 * 86400
        if crontab.hour != "*":
            return 86400
        if crontab.minute != "*":
            return 3600
        return 60
    return None


def list_scheduled_jobs():
    """Every periodic task with its schedule, last run and staleness.

    Returns an empty list when the beat scheduler is not installed — that is
    the case under the test settings, and on any deployment not running beat.
    """
    from django.apps import apps as django_apps
    from django.utils import timezone as dj_timezone

    if not django_apps.is_installed("django_celery_beat"):
        return []

    from django_celery_beat.models import PeriodicTask

    now = dj_timezone.now()
    jobs = []
    for task in PeriodicTask.objects.select_related("crontab", "interval").order_by("name"):
        if task.crontab:
            schedule_display = str(task.crontab)
        elif task.interval:
            schedule_display = f"every {task.interval.every} {task.interval.period}"
        else:
            schedule_display = "unknown"

        expected = _expected_interval_seconds(task)
        since = (now - task.last_run_at).total_seconds() if task.last_run_at else None
        # Two missed windows, not one: beat fires on a tick, so a single
        # period of slack is normal and would make everything look stale.
        is_stale = bool(task.enabled and expected and since is not None and since > expected * 2)

        jobs.append(
            {
                "id": task.id,
                "name": task.name,
                "task": task.task,
                "schedule_display": schedule_display,
                "enabled": task.enabled,
                "last_run_at": task.last_run_at,
                "total_run_count": task.total_run_count,
                "expected_interval_seconds": expected,
                "seconds_since_last_run": (int(since) if since is not None else None),
                "is_stale": is_stale,
            }
        )
    return jobs


def probe_celery_beat():
    """Derive beat liveness from the periodic-task table.

    There is no Celery result backend configured on this instance, so task
    history does not exist; ``last_run_at`` on the schedule is the only
    evidence that beat is alive.
    """
    try:
        jobs = list_scheduled_jobs()
    except Exception as exc:
        return _result(UNKNOWN, error=_sanitize(exc))

    enabled = [job for job in jobs if job["enabled"]]
    if not enabled:
        return _result(UNKNOWN, details={"enabled_task_count": 0}, error="No periodic tasks are enabled")

    run_times = [job["last_run_at"] for job in enabled if job["last_run_at"]]
    stale = [
        {
            "name": job["name"],
            "last_run_at": job["last_run_at"],
            "expected_interval_seconds": job["expected_interval_seconds"],
            "seconds_since_last_run": job["seconds_since_last_run"],
        }
        for job in enabled
        if job["is_stale"]
    ]
    last_run = max(run_times) if run_times else None
    elapsed = [job["seconds_since_last_run"] for job in enabled if job["seconds_since_last_run"] is not None]
    seconds_since = min(elapsed) if elapsed else None

    details = {
        "enabled_task_count": len(enabled),
        "last_run_at": last_run,
        "seconds_since_last_run": seconds_since,
        "stale_tasks": stale,
    }
    if last_run is None:
        return _result(UNKNOWN, details=details, error="No periodic task has run yet")
    return _result(DEGRADED if stale else OK, details=details)


def object_storage_client():
    """A boto3 S3 client built for probing, not for serving files.

    ``S3Storage`` is unsuitable here twice over: given a request it rewrites
    the endpoint to the *public* host, and it inherits botocore's defaults
    (60s connect, 60s read, 5 retries) — minutes of hang against a wedged
    MinIO.
    """
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION or None,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        config=Config(
            signature_version="s3v4",
            connect_timeout=2,
            read_timeout=5,
            retries={"max_attempts": 1},
        ),
    )


def probe_object_storage():
    """HEAD the uploads bucket. O(1) — never lists objects."""
    started = time.monotonic()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    details = {
        "backend": "minio" if settings.USE_MINIO else "s3",
        "bucket": bucket,
        "endpoint": settings.AWS_S3_ENDPOINT_URL or "aws",
    }
    try:
        object_storage_client().head_bucket(Bucket=bucket)
        return _result(OK, started, details=details)
    except Exception as exc:
        return _result(DOWN, started, error=_sanitize(exc), details=details)


def smtp_settings():
    """SMTP configuration, minus the password.

    SMTP is instance configuration rather than Django settings — it is edited
    in god-mode and stored (encrypted, for the password) in the database.
    """
    import os

    from plane.license.utils.instance_value import get_configuration_value

    try:
        (host, port, from_address, use_tls, use_ssl) = get_configuration_value(
            [
                {"key": "EMAIL_HOST", "default": os.environ.get("EMAIL_HOST")},
                {"key": "EMAIL_PORT", "default": os.environ.get("EMAIL_PORT")},
                {"key": "EMAIL_FROM", "default": os.environ.get("EMAIL_FROM")},
                {"key": "EMAIL_USE_TLS", "default": os.environ.get("EMAIL_USE_TLS", "1")},
                {"key": "EMAIL_USE_SSL", "default": os.environ.get("EMAIL_USE_SSL", "0")},
            ]
        )
    except Exception:
        return {"configured": False}

    return {
        "configured": bool(host),
        "host": host or None,
        "port": port or None,
        "from_address": from_address or None,
        "use_tls": use_tls == "1",
        "use_ssl": use_ssl == "1",
    }
