# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Instance-wide counts, and the telemetry extraction that produced them.

`telemetry_counts()` was lifted out of `license/bgtasks/tracer.py`, which
still emits every one of those numbers as a span attribute. If the two drift,
telemetry silently starts reporting something other than what it used to.
"""

import inspect
import uuid

import pytest

from plane.db.models import Project, User, Workspace
from plane.license.bgtasks import tracer
from plane.license.utils.instance_counts import instance_counts, telemetry_counts

# The span attributes tracer.instance_traces() sets from count queries.
TRACER_COUNT_ATTRIBUTES = [
    "user_count",
    "workspace_count",
    "project_count",
    "issue_count",
    "module_count",
    "cycle_count",
    "cycle_issue_count",
    "module_issue_count",
    "page_count",
]


@pytest.fixture
def seeded(db):
    owner = User.objects.create(
        email=f"counts-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
        display_name="counts-owner",
    )
    workspace = Workspace.objects.create(name="Counts WS", slug=f"counts-{uuid.uuid4().hex[:8]}", owner=owner)
    Project.objects.create(name="Regular", identifier="REG", workspace=workspace)
    Project.objects.create(name="Global", identifier="GLB", workspace=workspace, is_global=True)
    return workspace


def test_telemetry_counts_covers_every_attribute_the_tracer_reports():
    """Regression guard on the extraction.

    Anyone deleting a key from telemetry_counts() has to notice that the
    tracer still reads it.
    """
    source = inspect.getsource(tracer.instance_traces)
    for attribute in TRACER_COUNT_ATTRIBUTES:
        assert f'span.set_attribute("{attribute}"' in source, f"tracer no longer reports {attribute}"


@pytest.mark.django_db
def test_telemetry_counts_returns_exactly_the_expected_keys():
    assert set(telemetry_counts().keys()) == set(TRACER_COUNT_ATTRIBUTES)


def test_instance_counts_reports_the_seeded_entities(seeded):
    counts = instance_counts()

    assert counts["workspaces"] >= 1
    assert counts["projects"]["total"] >= 2
    assert counts["projects"]["global"] >= 1
    assert counts["users"]["total"] >= 1
    assert counts["users"]["active"] >= 1
    # Every panel the UI renders must have a key, even on a fresh instance.
    assert set(counts) >= {
        "workspaces",
        "users",
        "projects",
        "work_items",
        "cycles",
        "modules",
        "pages",
        "comments",
        "views",
        "labels",
        "attachments",
        "departments",
        "staff",
    }


def test_work_items_by_state_group_is_a_mapping(seeded):
    work_items = instance_counts()["work_items"]
    assert isinstance(work_items["by_state_group"], dict)
    assert work_items["total"] == sum(work_items["by_state_group"].values())
