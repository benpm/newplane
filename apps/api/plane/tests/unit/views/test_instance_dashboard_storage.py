# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Storage arithmetic for the instance dashboard.

`FileAsset.size` is declared by the client at presign time; the real byte
count only exists in `storage_metadata["ContentLength"]`, and only for assets
that finished the upload handshake. The rollup has to keep those apart and
survive whatever is actually in that unconstrained JSON column.
"""

import uuid

import pytest

from plane.db.models import FileAsset, User, Workspace
from plane.utils.instance_storage import asset_storage_rollup, postgres_sizes


@pytest.fixture
def workspace(db):
    owner = User.objects.create(
        email=f"storage-owner-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
        display_name="storage-owner",
    )
    return Workspace.objects.create(name="Storage WS", slug=f"storage-{uuid.uuid4().hex[:8]}", owner=owner)


def _asset(workspace, *, size, metadata=None, uploaded=True, deleted=False):
    return FileAsset.objects.create(
        workspace=workspace,
        attributes={},
        asset=f"uploads/{uuid.uuid4().hex}",
        size=size,
        is_uploaded=uploaded,
        is_deleted=deleted,
        storage_metadata=metadata if metadata is not None else {},
        entity_type="ISSUE_ATTACHMENT",
    )


def test_rollup_separates_declared_measured_pending_and_deleted(workspace):
    _asset(workspace, size=1000, metadata={"ContentLength": 900})
    _asset(workspace, size=2000, metadata={"ContentLength": 1800})
    _asset(workspace, size=500)  # uploaded, but never measured
    _asset(workspace, size=4000, uploaded=False)  # reserved, never arrived
    _asset(workspace, size=250, deleted=True)  # awaiting cleanup

    rollup = asset_storage_rollup()

    assert rollup["declared_bytes"] == 3500  # 1000 + 2000 + 500
    assert rollup["measured_bytes"] == 2700  # 900 + 1800
    assert rollup["uploaded_count"] == 3
    assert rollup["measured_count"] == 2
    assert rollup["measured_coverage"] == pytest.approx(2 / 3, abs=1e-4)
    assert rollup["pending_bytes"] == 4000
    assert rollup["pending_count"] == 1
    assert rollup["soft_deleted_bytes"] == 250
    assert rollup["soft_deleted_count"] == 1


def test_non_numeric_content_length_does_not_break_the_aggregate(workspace):
    """storage_metadata is unconstrained JSON.

    Without the numeric guard in the SQL, one row like this raises
    `invalid input syntax for type bigint` and takes the whole panel down.
    """
    _asset(workspace, size=1000, metadata={"ContentLength": 900})
    _asset(workspace, size=2000, metadata={"ContentLength": "not-a-number"})
    _asset(workspace, size=3000, metadata={"ContentLength": ""})
    _asset(workspace, size=4000, metadata={"ContentLength": None})

    rollup = asset_storage_rollup()

    # Only the one parseable value counts as measured; the rest fall back to
    # their declared size in the best-effort rollups.
    assert rollup["measured_bytes"] == 900
    assert rollup["measured_count"] == 1
    assert rollup["declared_bytes"] == 10000

    by_workspace = {row["workspace_slug"]: row for row in rollup["by_workspace"]}
    assert by_workspace[workspace.slug]["best_effort_bytes"] == 900 + 2000 + 3000 + 4000


def test_rollup_groups_by_workspace_and_entity_type(workspace):
    _asset(workspace, size=100, metadata={"ContentLength": 100})
    _asset(workspace, size=200, metadata={"ContentLength": 200})

    rollup = asset_storage_rollup()

    by_workspace = {row["workspace_slug"]: row for row in rollup["by_workspace"]}
    assert by_workspace[workspace.slug]["count"] == 2
    assert by_workspace[workspace.slug]["best_effort_bytes"] == 300

    by_entity = {row["entity_type"]: row for row in rollup["by_entity_type"]}
    assert by_entity["ISSUE_ATTACHMENT"]["count"] == 2


def test_empty_instance_reports_zeros_not_nulls(db):
    rollup = asset_storage_rollup()

    assert rollup["declared_bytes"] == 0
    assert rollup["measured_bytes"] == 0
    assert rollup["measured_coverage"] is None  # no assets => coverage undefined
    assert rollup["by_workspace"] == []


def test_postgres_sizes_reports_the_database_and_its_largest_tables(db):
    sizes = postgres_sizes(limit=5)

    assert sizes["database_size_bytes"] > 0
    assert 0 < len(sizes["largest_tables"]) <= 5
    first = sizes["largest_tables"][0]
    assert {"table", "total_bytes", "table_bytes", "index_bytes", "row_estimate"} <= set(first)
    # Ordered by total size, largest first.
    totals = [table["total_bytes"] for table in sizes["largest_tables"]]
    assert totals == sorted(totals, reverse=True)
