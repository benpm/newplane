# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the Discord handle on a user profile.

The handle is written through ``PATCH /api/users/me/`` and read back on the
workspace profile page, which builds its payload by hand rather than through
``UserLiteSerializer`` -- so the two ends are wired separately and a change to
one does not carry the other.
"""

import pytest
from rest_framework.test import APIClient

from plane.app.permissions import ROLE
from plane.tests.factories import UserFactory, WorkspaceFactory, WorkspaceMemberFactory

ME_URL = "/api/users/me/"
PROFILE_URL = "/api/workspaces/{slug}/user-profile/{user_id}/"


@pytest.fixture
def user(db):
    return UserFactory()


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.unit
@pytest.mark.django_db
class TestDiscordUsername:
    def test_it_can_be_set(self, user):
        resp = _client(user).patch(ME_URL, {"discord_username": "jane.doe"}, format="json")
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.discord_username == "jane.doe"

    def test_it_can_be_cleared(self, user):
        user.discord_username = "jane.doe"
        user.save(update_fields=["discord_username"])

        resp = _client(user).patch(ME_URL, {"discord_username": ""}, format="json")
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.discord_username == ""

    @pytest.mark.parametrize(
        "handle",
        [
            "Jane.Doe",  # uppercase is not a legal Discord handle
            "jane doe",  # spaces
            "jane#1234",  # the retired discriminator format
            "j",  # under the 2 character minimum
            "j" * 33,  # over the 32 character maximum
        ],
    )
    def test_malformed_handles_are_refused(self, user, handle):
        resp = _client(user).patch(ME_URL, {"discord_username": handle}, format="json")
        assert resp.status_code == 400

    def test_it_is_returned_by_the_me_endpoint(self, user):
        user.discord_username = "jane.doe"
        user.save(update_fields=["discord_username"])

        resp = _client(user).get(ME_URL)
        assert resp.status_code == 200
        assert resp.json()["discord_username"] == "jane.doe"


@pytest.mark.unit
@pytest.mark.django_db
class TestDiscordUsernameOnProfilePage:
    def test_it_reaches_the_profile_payload(self):
        """The profile sidebar reads user_data, which is assembled by hand."""
        viewer = UserFactory()
        subject = UserFactory(discord_username="jane.doe")

        workspace = WorkspaceFactory(owner=viewer)
        WorkspaceMemberFactory(workspace=workspace, member=viewer, role=ROLE.ADMIN.value)
        WorkspaceMemberFactory(workspace=workspace, member=subject, role=ROLE.MEMBER.value)

        resp = _client(viewer).get(PROFILE_URL.format(slug=workspace.slug, user_id=subject.id))
        assert resp.status_code == 200
        assert resp.json()["user_data"]["discord_username"] == "jane.doe"
