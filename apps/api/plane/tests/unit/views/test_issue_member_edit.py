# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Who may PATCH a work item through the app layer.

Members edit any work item in their project (changing its status from the list or
board must not depend on having created or been assigned to it); guests edit only
work items they created.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from plane.app.permissions import ROLE
from plane.db.models import Issue, State
from plane.tests.factories import (
    ProjectFactory,
    ProjectMemberFactory,
    UserFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
)

ISSUE_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/{pk}/"


@pytest.fixture
def workspace(db):
    owner = UserFactory()
    ws = WorkspaceFactory(owner=owner)
    WorkspaceMemberFactory(workspace=ws, member=owner, role=ROLE.ADMIN.value)
    return ws


@pytest.fixture
def project(workspace):
    return ProjectFactory(workspace=workspace, created_by=workspace.owner, updated_by=workspace.owner)


@pytest.fixture
def states(project, workspace):
    return [
        State.objects.create(project=project, workspace=workspace, name=name, group=group, color="#000000")
        for name, group in (("Todo", "unstarted"), ("Doing", "started"))
    ]


@pytest.fixture
def issue(project, workspace, states):
    """A work item created by the workspace owner, with no assignees."""
    item = Issue(project=project, workspace=workspace, name="Someone else's item", state=states[0])
    item.save(created_by_id=workspace.owner.id)
    return item


def _project_user(workspace, project, role):
    user = UserFactory()
    WorkspaceMemberFactory(workspace=workspace, member=user, role=role)
    ProjectMemberFactory(project=project, member=user, role=role)
    return user


def _patch_state(user, issue, state):
    client = APIClient()
    client.force_authenticate(user=user)
    with (
        patch("plane.bgtasks.webhook_task.model_activity.delay"),
        patch("plane.bgtasks.issue_description_version_task.issue_description_version_task.delay"),
        patch("plane.bgtasks.discord_task.send_discord_notification_task.delay"),
    ):
        return client.patch(
            ISSUE_URL.format(slug=issue.workspace.slug, project_id=issue.project_id, pk=issue.id),
            {"state_id": str(state.id)},
            format="json",
        )


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueEditRoles:
    def test_member_changes_state_of_item_they_did_not_create(self, workspace, project, states, issue):
        member = _project_user(workspace, project, ROLE.MEMBER.value)

        resp = _patch_state(member, issue, states[1])

        assert resp.status_code == 204, resp.content
        issue.refresh_from_db()
        assert issue.state_id == states[1].id

    def test_guest_cannot_change_state_of_item_they_did_not_create(self, workspace, project, states, issue):
        guest = _project_user(workspace, project, ROLE.GUEST.value)

        resp = _patch_state(guest, issue, states[1])

        assert resp.status_code == 403, resp.content
        issue.refresh_from_db()
        assert issue.state_id == states[0].id
