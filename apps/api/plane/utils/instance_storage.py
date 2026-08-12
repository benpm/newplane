# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Storage measurement for the instance dashboard.

Three sources describe how much space this instance uses, and they disagree:

``FileAsset.size``
    Client-*declared* at presign time and clamped to ``FILE_SIZE_LIMIT``
    (see ``plane/app/views/asset/v2.py``). A reservation, not a measurement.

``FileAsset.storage_metadata["ContentLength"]``
    A real ``head_object`` reading, but only present on assets that completed
    the v2 upload handshake. Authoritative where it exists, absent elsewhere.

A bucket scan
    Ground truth for bytes on disk, and the only source that sees objects with
    no row behind them.

The helpers below keep the three apart and report ``measured_coverage`` so the
UI can say how much of the number is measured rather than declared. Blending
them into one figure would be a lie with a plausible face.
"""

import time

from django.conf import settings
from django.db import connection

# The uploaded, live population every headline number is computed over.
_LIVE_ASSETS = "fa.is_uploaded AND NOT fa.is_deleted AND fa.deleted_at IS NULL"

# storage_metadata is an unconstrained JSONField. One row with a non-numeric
# ContentLength would abort the whole aggregate with a cast error, so every
# read of it is gated on the value actually looking like an integer.
_MEASURED_BYTES = """
    CASE WHEN fa.storage_metadata->>'ContentLength' ~ '^[0-9]+$'
         THEN (fa.storage_metadata->>'ContentLength')::bigint END
"""

_BEST_EFFORT_BYTES = f"COALESCE({_MEASURED_BYTES}, fa.size::bigint)"


def postgres_sizes(limit=15):
    """Total database size plus the largest tables.

    Catalog-only: ``pg_total_relation_size`` reads metadata, it does not scan
    the tables. ``reltuples`` is an estimate left by the last ANALYZE, which
    is why it is named ``row_estimate`` all the way through to the UI.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        database_size = int(cursor.fetchone()[0])

        cursor.execute(
            """
            SELECT c.oid::regclass::text,
                   pg_total_relation_size(c.oid),
                   pg_table_size(c.oid),
                   pg_indexes_size(c.oid),
                   c.reltuples::bigint
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT %s
            """,
            [limit],
        )
        largest = [
            {
                "table": row[0],
                "total_bytes": int(row[1]),
                "table_bytes": int(row[2]),
                "index_bytes": int(row[3]),
                "row_estimate": max(int(row[4]), 0),
            }
            for row in cursor.fetchall()
        ]

    return {"database_size_bytes": database_size, "largest_tables": largest}


def asset_storage_rollup(workspace_limit=25):
    """Per-instance, per-entity and per-workspace file-asset totals."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
              COALESCE(SUM(fa.size) FILTER (WHERE {_LIVE_ASSETS}), 0),
              COALESCE(SUM({_MEASURED_BYTES}) FILTER (WHERE {_LIVE_ASSETS}), 0),
              COUNT(*) FILTER (WHERE {_LIVE_ASSETS}),
              COUNT(*) FILTER (WHERE {_LIVE_ASSETS} AND {_MEASURED_BYTES} IS NOT NULL),
              COALESCE(SUM(fa.size) FILTER (WHERE NOT fa.is_uploaded), 0),
              COUNT(*) FILTER (WHERE NOT fa.is_uploaded),
              COALESCE(SUM(fa.size) FILTER (WHERE fa.is_deleted OR fa.deleted_at IS NOT NULL), 0),
              COUNT(*) FILTER (WHERE fa.is_deleted OR fa.deleted_at IS NOT NULL)
            FROM file_assets fa
            """
        )
        (
            declared,
            measured,
            uploaded_count,
            measured_count,
            pending,
            pending_count,
            soft_deleted,
            soft_deleted_count,
        ) = cursor.fetchone()

        cursor.execute(
            f"""
            SELECT fa.entity_type, COUNT(*), COALESCE(SUM({_BEST_EFFORT_BYTES}), 0)
            FROM file_assets fa
            WHERE {_LIVE_ASSETS}
            GROUP BY fa.entity_type
            ORDER BY 3 DESC
            """
        )
        by_entity_type = [
            {"entity_type": row[0] or "UNKNOWN", "count": row[1], "best_effort_bytes": int(row[2])}
            for row in cursor.fetchall()
        ]

        cursor.execute(
            f"""
            SELECT w.id, w.slug, w.name, COUNT(*), COALESCE(SUM({_BEST_EFFORT_BYTES}), 0)
            FROM file_assets fa
            JOIN workspaces w ON w.id = fa.workspace_id
            WHERE {_LIVE_ASSETS}
            GROUP BY w.id, w.slug, w.name
            ORDER BY 5 DESC
            LIMIT %s
            """,
            [workspace_limit],
        )
        by_workspace = [
            {
                "workspace_id": str(row[0]),
                "workspace_slug": row[1],
                "workspace_name": row[2],
                "count": row[3],
                "best_effort_bytes": int(row[4]),
            }
            for row in cursor.fetchall()
        ]

    return {
        "declared_bytes": int(declared),
        "measured_bytes": int(measured),
        "measured_coverage": (round(measured_count / uploaded_count, 4) if uploaded_count else None),
        "uploaded_count": uploaded_count,
        "measured_count": measured_count,
        "pending_bytes": int(pending),
        "pending_count": pending_count,
        "soft_deleted_bytes": int(soft_deleted),
        "soft_deleted_count": soft_deleted_count,
        "by_entity_type": by_entity_type,
        "by_workspace": by_workspace,
    }


# A scan is bounded by both a clock and an object count: it is the only
# operation here whose cost grows without limit, and an admin should never be
# able to hang a request thread by clicking a button.
SCAN_TIME_BUDGET_SECONDS = 20
SCAN_OBJECT_LIMIT = 500_000


def scan_bucket():
    """Walk the uploads bucket for a true object count and byte total.

    Returns ``truncated: True`` when either cap is hit, in which case the
    totals are a lower bound and the UI must say so.
    """
    from plane.utils.instance_probes import object_storage_client

    started = time.monotonic()
    client = object_storage_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME

    object_count = 0
    total_bytes = 0
    truncated = False

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, PaginationConfig={"PageSize": 1000}):
        for obj in page.get("Contents", []):
            object_count += 1
            total_bytes += obj["Size"]
        if time.monotonic() - started > SCAN_TIME_BUDGET_SECONDS or object_count >= SCAN_OBJECT_LIMIT:
            truncated = True
            break

    return {
        "status": "fresh",
        "bucket": bucket,
        "object_count": object_count,
        "total_bytes": total_bytes,
        "truncated": truncated,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
    }
