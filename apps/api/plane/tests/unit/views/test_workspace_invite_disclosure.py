# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for what the public invite endpoint discloses.

The join endpoint is intentionally reachable without authentication so an
invitee can see who invited them before signing in. That makes its response
body a public surface: the acceptance token decides who may join the
workspace, so it must never appear there, in any field.
"""

import pytest
from rest_framework.test import APIClient

from plane.app.permissions import ROLE
from plane.db.models import WorkspaceMemberInvite
from plane.tests.factories import UserFactory, WorkspaceFactory, WorkspaceMemberFactory

JOIN_URL = "/api/workspaces/{slug}/invitations/{pk}/join/"


@pytest.fixture
def workspace(db):
    owner = UserFactory()
    ws = WorkspaceFactory(owner=owner)
    WorkspaceMemberFactory(workspace=ws, member=owner, role=ROLE.ADMIN.value)
    return ws


@pytest.fixture
def invitation(workspace):
    return WorkspaceMemberInvite.objects.create(
        workspace=workspace,
        email="invitee@plane.so",
        token="super-secret-token",
        role=ROLE.MEMBER.value,
        message="Join us",
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestPublicInviteDisclosure:
    def _get(self, workspace, invitation):
        return APIClient().get(JOIN_URL.format(slug=workspace.slug, pk=invitation.id))

    def test_unauthenticated_callers_can_read_the_invitation(self, workspace, invitation):
        """The endpoint stays open; this test guards the redaction, not access."""
        resp = self._get(workspace, invitation)
        assert resp.status_code == 200
        assert resp.json()["email"] == "invitee@plane.so"

    def test_the_acceptance_token_is_not_returned(self, workspace, invitation):
        assert "token" not in self._get(workspace, invitation).json()

    def test_no_field_leaks_the_token_value(self, workspace, invitation):
        """A link or any other field embedding the token is just as disclosing."""
        assert "super-secret-token" not in self._get(workspace, invitation).content.decode()

    def test_the_invite_link_is_not_returned(self, workspace, invitation):
        assert "invite_link" not in self._get(workspace, invitation).json()

    def test_the_useful_context_is_still_present(self, workspace, invitation):
        """Redaction must not strip what the invitee needs to decide."""
        body = self._get(workspace, invitation).json()
        assert body["workspace"]["slug"] == workspace.slug
        assert body["message"] == "Join us"
        assert body["accepted"] is False
