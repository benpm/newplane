# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""User management from the instance dashboard.

Renaming, deactivation and named invite links. The deactivation guards matter
most: an admin who locks themselves or the last super admin out needs shell
access to recover.
"""

import uuid

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import User, Workspace, WorkspaceMember, WorkspaceMemberInvite
from plane.license.models import Instance, InstanceAdmin


def _make_user(prefix: str, **kwargs) -> User:
    return User.objects.create(
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
        display_name=prefix,
        **kwargs,
    )


@pytest.fixture
def instance(db):
    return Instance.objects.create(
        instance_name="Test Instance",
        is_setup_done=True,
        last_checked_at=timezone.now(),
    )


@pytest.fixture
def admin_user(db, instance):
    user = _make_user("dash-admin")
    InstanceAdmin.objects.create(instance=instance, user=user, role=20, is_super_admin=True)
    return user


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    return api


@pytest.fixture
def workspace(db, admin_user):
    return Workspace.objects.create(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner=admin_user)


# --------------------------------------------------------------- renaming


def test_rename_changes_the_display_name_only(client, db):
    user = _make_user("before")
    original_username, original_email = user.username, user.email

    url = reverse("instance-dashboard-user-detail", args=[user.id])
    response = client.patch(url, {"display_name": "After Rename"}, format="json")

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.display_name == "After Rename"
    # The identity and login key are untouched — that was the whole point.
    assert user.username == original_username
    assert user.email == original_email


def test_rename_trims_and_rejects_blank(client, db):
    user = _make_user("keepme")
    url = reverse("instance-dashboard-user-detail", args=[user.id])

    assert client.patch(url, {"display_name": "  Padded  "}, format="json").status_code == 200
    user.refresh_from_db()
    assert user.display_name == "Padded"

    assert client.patch(url, {"display_name": "   "}, format="json").status_code == 400
    user.refresh_from_db()
    assert user.display_name == "Padded"


def test_rename_of_a_missing_user_is_404(client, db):
    url = reverse("instance-dashboard-user-detail", args=[uuid.uuid4()])
    assert client.patch(url, {"display_name": "Nobody"}, format="json").status_code == 404


# ----------------------------------------------------------- deactivation


def test_deactivation_also_suspends_workspace_membership(client, db, workspace):
    user = _make_user("member")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)

    url = reverse("instance-dashboard-user-detail", args=[user.id])
    assert client.patch(url, {"is_active": False}, format="json").status_code == 200

    user.refresh_from_db()
    assert user.is_active is False
    assert WorkspaceMember.objects.get(workspace=workspace, member=user).is_active is False


def test_deactivation_is_reversible(client, db, workspace):
    user = _make_user("returning")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)
    url = reverse("instance-dashboard-user-detail", args=[user.id])

    client.patch(url, {"is_active": False}, format="json")
    assert client.patch(url, {"is_active": True}, format="json").status_code == 200

    user.refresh_from_db()
    assert user.is_active is True
    assert WorkspaceMember.objects.get(workspace=workspace, member=user).is_active is True


def test_deactivation_preserves_authored_content(client, db, workspace):
    """The reason this is deactivation and not a delete.

    User is not soft-deletable and Django cascades in Python, so `.delete()`
    would take the account's work items, pages and projects with it.
    """
    user = _make_user("author")
    project_count_before = Workspace.objects.count()

    url = reverse("instance-dashboard-user-detail", args=[user.id])
    client.patch(url, {"is_active": False}, format="json")

    assert User.objects.filter(pk=user.pk).exists()
    assert Workspace.objects.count() == project_count_before


def test_cannot_deactivate_yourself(client, admin_user):
    url = reverse("instance-dashboard-user-detail", args=[admin_user.id])
    response = client.patch(url, {"is_active": False}, format="json")

    assert response.status_code == 400
    admin_user.refresh_from_db()
    assert admin_user.is_active is True


def test_cannot_deactivate_the_last_super_admin(db, instance):
    """Two admins: one acting, one the sole *other* super admin.

    Removing the last super admin who can sign in would lock God Mode with no
    in-app way back.
    """
    acting = _make_user("acting")
    InstanceAdmin.objects.create(instance=instance, user=acting, role=20, is_super_admin=False)

    only_super = _make_user("only-super")
    InstanceAdmin.objects.create(instance=instance, user=only_super, role=20, is_super_admin=True)

    api = APIClient()
    api.force_authenticate(user=acting)
    url = reverse("instance-dashboard-user-detail", args=[only_super.id])
    response = api.patch(url, {"is_active": False}, format="json")

    assert response.status_code == 400
    only_super.refresh_from_db()
    assert only_super.is_active is True


def test_a_super_admin_can_be_deactivated_when_another_remains(db, instance):
    acting = _make_user("acting-super")
    InstanceAdmin.objects.create(instance=instance, user=acting, role=20, is_super_admin=True)
    spare = _make_user("spare-super")
    InstanceAdmin.objects.create(instance=instance, user=spare, role=20, is_super_admin=True)

    api = APIClient()
    api.force_authenticate(user=acting)
    url = reverse("instance-dashboard-user-detail", args=[spare.id])

    assert api.patch(url, {"is_active": False}, format="json").status_code == 200


# ---------------------------------------------------------------- invites


def test_creating_a_named_invite_returns_a_usable_link(client, db, workspace):
    response = client.post(
        reverse("instance-dashboard-invites"),
        {"email": "New.Person@Example.com", "display_name": "New Person", "workspace_id": str(workspace.id), "role": 15},
        format="json",
    )

    assert response.status_code == 201
    body = response.data
    assert body["email"] == "new.person@example.com"  # normalised
    assert body["display_name"] == "New Person"

    invite = WorkspaceMemberInvite.objects.get(pk=body["id"])
    # The link must carry all three parameters the join endpoint validates.
    assert f"invitation_id={invite.id}" in body["link"]
    assert f"slug={workspace.slug}" in body["link"]
    assert f"token={invite.token}" in body["link"]


def test_reinviting_updates_rather_than_colliding(client, db, workspace):
    """(email, workspace) is unique — a second invite must not 500."""
    payload = {"email": "again@example.com", "display_name": "First Spelling", "workspace_id": str(workspace.id)}
    first = client.post(reverse("instance-dashboard-invites"), payload, format="json")
    assert first.status_code == 201

    second = client.post(
        reverse("instance-dashboard-invites"),
        {**payload, "display_name": "Corrected Spelling", "role": 20},
        format="json",
    )
    assert second.status_code == 200
    assert second.data["reused"] is True
    assert second.data["id"] == first.data["id"]
    assert second.data["display_name"] == "Corrected Spelling"
    assert second.data["role"] == 20
    assert WorkspaceMemberInvite.objects.filter(email="again@example.com", workspace=workspace).count() == 1


def test_invite_rejects_an_existing_member(client, db, workspace):
    member = _make_user("already")
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15, is_active=True)

    response = client.post(
        reverse("instance-dashboard-invites"),
        {"email": member.email, "workspace_id": str(workspace.id)},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"workspace_id": "x"}, 400),  # no email
        ({"email": "a@b.com"}, 400),  # no workspace
        ({"email": "a@b.com", "workspace_id": str(uuid.uuid4())}, 404),  # unknown workspace
        ({"email": "a@b.com", "workspace_id": "not-a-uuid"}, 404),  # malformed id
    ],
)
def test_invite_validation(client, db, payload, expected):
    assert client.post(reverse("instance-dashboard-invites"), payload, format="json").status_code == expected


def test_invite_rejects_an_unknown_role(client, db, workspace):
    response = client.post(
        reverse("instance-dashboard-invites"),
        {"email": "role@example.com", "workspace_id": str(workspace.id), "role": 99},
        format="json",
    )
    assert response.status_code == 400


def test_listing_shows_only_outstanding_invites(client, db, workspace):
    pending = WorkspaceMemberInvite.objects.create(
        email="pending@example.com", workspace=workspace, token=uuid.uuid4().hex, role=15
    )
    WorkspaceMemberInvite.objects.create(
        email="done@example.com",
        workspace=workspace,
        token=uuid.uuid4().hex,
        role=15,
        responded_at=timezone.now(),
    )

    response = client.get(reverse("instance-dashboard-invites"))
    assert response.status_code == 200
    ids = [row["id"] for row in response.data["results"]]
    assert ids == [str(pending.id)]


def test_revoking_an_invite(client, db, workspace):
    invite = WorkspaceMemberInvite.objects.create(
        email="revoke@example.com", workspace=workspace, token=uuid.uuid4().hex, role=15
    )
    url = reverse("instance-dashboard-invite-detail", args=[invite.id])

    assert client.delete(url).status_code == 204
    assert not WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()


def test_cannot_revoke_an_answered_invite(client, db, workspace):
    invite = WorkspaceMemberInvite.objects.create(
        email="answered@example.com",
        workspace=workspace,
        token=uuid.uuid4().hex,
        role=15,
        responded_at=timezone.now(),
    )
    url = reverse("instance-dashboard-invite-detail", args=[invite.id])
    assert client.delete(url).status_code == 400


# ------------------------------------------------- name applied on accept


def test_invited_name_is_adopted_when_the_account_never_chose_one(db, workspace):
    from plane.app.views.workspace.invite import _apply_invited_display_name

    user = User.objects.create(email="derived@example.com", username=uuid.uuid4().hex)
    user.save()  # the model derives display_name from the email local part
    assert user.display_name == "derived"

    invite = WorkspaceMemberInvite.objects.create(
        email="derived@example.com",
        workspace=workspace,
        token=uuid.uuid4().hex,
        role=15,
        display_name="Real Name",
    )
    _apply_invited_display_name(user, invite)

    user.refresh_from_db()
    assert user.display_name == "Real Name"


def test_invited_name_never_overwrites_a_self_chosen_one(db, workspace):
    """A second invite must not rewrite a name the person picked themselves."""
    from plane.app.views.workspace.invite import _apply_invited_display_name

    user = User.objects.create(email="chosen@example.com", username=uuid.uuid4().hex, display_name="Their Own Name")
    invite = WorkspaceMemberInvite.objects.create(
        email="chosen@example.com",
        workspace=workspace,
        token=uuid.uuid4().hex,
        role=15,
        display_name="Imposed Name",
    )

    _apply_invited_display_name(user, invite)

    user.refresh_from_db()
    assert user.display_name == "Their Own Name"


def test_unnamed_invite_leaves_the_account_alone(db, workspace):
    from plane.app.views.workspace.invite import _apply_invited_display_name

    user = User.objects.create(email="plain@example.com", username=uuid.uuid4().hex)
    user.save()
    invite = WorkspaceMemberInvite.objects.create(
        email="plain@example.com", workspace=workspace, token=uuid.uuid4().hex, role=15
    )

    _apply_invited_display_name(user, invite)

    user.refresh_from_db()
    assert user.display_name == "plain"
