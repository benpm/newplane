# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the reusable workspace invite link.

Two properties matter and neither is covered anywhere else. First, the link is
*reusable* -- that is the whole reason it exists, and a single-use regression
would look identical to a working link right up until the second person tried
it. Second, the public endpoint is unauthenticated, so its response body is a
public surface and must never carry the token: whoever holds the token can join
the workspace.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.app.permissions import ROLE
from plane.authentication.utils.invite_link import redeem_invite_link
from plane.db.models import WorkspaceInviteLink, WorkspaceMember
from plane.tests.factories import UserFactory, WorkspaceFactory, WorkspaceMemberFactory

LINK_URL = "/api/workspaces/{slug}/invite-link/"
PUBLIC_URL = "/api/invite-links/{token}/"


@pytest.fixture
def admin_user(db):
    return UserFactory()


@pytest.fixture
def workspace(admin_user):
    ws = WorkspaceFactory(owner=admin_user)
    WorkspaceMemberFactory(workspace=ws, member=admin_user, role=ROLE.ADMIN.value)
    return ws


@pytest.fixture
def member_user(workspace):
    user = UserFactory()
    WorkspaceMemberFactory(workspace=workspace, member=user, role=ROLE.MEMBER.value)
    return user


@pytest.fixture
def invite_link(workspace):
    return WorkspaceInviteLink.objects.create(
        workspace=workspace, token=uuid.uuid4().hex, role=ROLE.MEMBER.value
    )


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


@pytest.mark.unit
@pytest.mark.django_db
class TestInviteLinkManagement:
    def test_admin_can_create_a_link(self, workspace, admin_user):
        resp = _client(admin_user).post(LINK_URL.format(slug=workspace.slug), {"role": ROLE.MEMBER.value})
        assert resp.status_code == 201
        assert resp.json()["role"] == ROLE.MEMBER.value
        assert resp.json()["token"]

    def test_plain_member_cannot_create_a_link(self, workspace, member_user):
        resp = _client(member_user).post(LINK_URL.format(slug=workspace.slug), {"role": ROLE.MEMBER.value})
        assert resp.status_code == 403

    def test_anonymous_cannot_create_a_link(self, workspace):
        resp = _client().post(LINK_URL.format(slug=workspace.slug), {"role": ROLE.MEMBER.value})
        assert resp.status_code in (401, 403)

    def test_role_must_be_a_known_role(self, workspace, admin_user):
        resp = _client(admin_user).post(LINK_URL.format(slug=workspace.slug), {"role": 99})
        assert resp.status_code == 400

    def test_creating_a_link_retires_the_previous_one(self, workspace, admin_user, invite_link):
        resp = _client(admin_user).post(LINK_URL.format(slug=workspace.slug), {"role": ROLE.MEMBER.value})
        assert resp.status_code == 201

        invite_link.refresh_from_db()
        assert invite_link.is_active is False, "the superseded token must stop working"
        assert resp.json()["token"] != invite_link.token

    def test_revoking_deactivates_the_link(self, workspace, admin_user, invite_link):
        resp = _client(admin_user).delete(LINK_URL.format(slug=workspace.slug))
        assert resp.status_code == 204

        invite_link.refresh_from_db()
        assert invite_link.is_active is False


@pytest.mark.unit
@pytest.mark.django_db
class TestPublicInviteLinkDisclosure:
    def test_unauthenticated_callers_can_read_the_workspace_name(self, invite_link):
        resp = _client().get(PUBLIC_URL.format(token=invite_link.token))
        assert resp.status_code == 200
        assert resp.json()["workspace_name"] == invite_link.workspace.name

    def test_the_token_is_never_disclosed(self, invite_link):
        """The endpoint is open, so anything here is public. The token is not."""
        resp = _client().get(PUBLIC_URL.format(token=invite_link.token))
        assert resp.status_code == 200

        body = resp.json()
        assert "token" not in body
        assert invite_link.token not in str(body), "the token leaked through some other field"

    def test_a_revoked_link_is_not_found(self, invite_link):
        invite_link.is_active = False
        invite_link.save(update_fields=["is_active"])

        resp = _client().get(PUBLIC_URL.format(token=invite_link.token))
        assert resp.status_code == 404

    def test_an_unknown_token_is_not_found(self):
        resp = _client().get(PUBLIC_URL.format(token=uuid.uuid4().hex))
        assert resp.status_code == 404

    def test_opening_a_link_parks_the_token_on_the_session(self, invite_link):
        """This is what lets the sign-up that follows know which workspace to join."""
        client = _client()
        client.get(PUBLIC_URL.format(token=invite_link.token))
        assert client.session.get("invite_link_token") == invite_link.token


class _FakeRequest:
    """Carries just the session attribute that redemption reads."""

    def __init__(self, session):
        self.session = session


@pytest.mark.unit
@pytest.mark.django_db
class TestInviteLinkRedemption:
    def test_redemption_grants_the_links_role(self, invite_link):
        user = UserFactory()
        redeem_invite_link(user=user, request=_FakeRequest({"invite_link_token": invite_link.token}))

        membership = WorkspaceMember.objects.get(workspace=invite_link.workspace, member=user)
        assert membership.role == ROLE.MEMBER.value
        assert membership.is_active is True

    def test_the_same_link_works_for_more_than_one_person(self, invite_link):
        """The reusability guarantee -- the reason this model exists at all."""
        first, second = UserFactory(), UserFactory()

        redeem_invite_link(user=first, request=_FakeRequest({"invite_link_token": invite_link.token}))
        redeem_invite_link(user=second, request=_FakeRequest({"invite_link_token": invite_link.token}))

        joined = WorkspaceMember.objects.filter(workspace=invite_link.workspace, member__in=[first, second])
        assert joined.count() == 2

        invite_link.refresh_from_db()
        assert invite_link.uses == 2

    def test_redeeming_twice_does_not_duplicate_membership(self, invite_link):
        user = UserFactory()
        redeem_invite_link(user=user, request=_FakeRequest({"invite_link_token": invite_link.token}))
        redeem_invite_link(user=user, request=_FakeRequest({"invite_link_token": invite_link.token}))

        assert WorkspaceMember.objects.filter(workspace=invite_link.workspace, member=user).count() == 1

    def test_an_existing_members_role_is_left_alone(self, workspace, member_user):
        """A guest link must not be able to demote a sitting admin."""
        guest_link = WorkspaceInviteLink.objects.create(
            workspace=workspace, token=uuid.uuid4().hex, role=ROLE.GUEST.value
        )
        redeem_invite_link(user=member_user, request=_FakeRequest({"invite_link_token": guest_link.token}))

        membership = WorkspaceMember.objects.get(workspace=workspace, member=member_user)
        assert membership.role == ROLE.MEMBER.value

    def test_a_removed_member_is_reinstated(self, workspace, member_user, invite_link):
        membership = WorkspaceMember.objects.get(workspace=workspace, member=member_user)
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        redeem_invite_link(user=member_user, request=_FakeRequest({"invite_link_token": invite_link.token}))

        membership.refresh_from_db()
        assert membership.is_active is True

    def test_a_revoked_link_grants_nothing(self, invite_link):
        invite_link.is_active = False
        invite_link.save(update_fields=["is_active"])

        user = UserFactory()
        redeem_invite_link(user=user, request=_FakeRequest({"invite_link_token": invite_link.token}))

        assert not WorkspaceMember.objects.filter(workspace=invite_link.workspace, member=user).exists()

    def test_the_token_is_consumed_from_the_session(self, invite_link):
        """Left in place it would re-run on every later sign-in."""
        session = {"invite_link_token": invite_link.token}
        redeem_invite_link(user=UserFactory(), request=_FakeRequest(session))
        assert "invite_link_token" not in session

    def test_no_token_is_a_no_op(self):
        assert redeem_invite_link(user=UserFactory(), request=_FakeRequest({})) is None
