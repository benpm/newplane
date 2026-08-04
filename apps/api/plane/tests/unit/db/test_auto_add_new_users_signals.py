# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from uuid import uuid4

from plane.db.models import (
    Project,
    ProjectMember,
    ProjectUserProperty,
    User,
    Workspace,
    WorkspaceMember,
)

PROJECT_MEMBER_ROLE = 15
PROJECT_ADMIN_ROLE = 20
GUEST_ROLE = 5


def make_workspace(owner):
    return Workspace.objects.create(name="Auto Add WS", slug=f"auto-add-{uuid4().hex[:8]}", id=uuid4(), owner=owner)


def make_project(workspace, owner, auto_add_new_users):
    return Project.objects.create(
        name="Auto Add Project",
        identifier=uuid4().hex[:6].upper(),
        workspace=workspace,
        created_by=owner,
        auto_add_new_users=auto_add_new_users,
    )


def make_user(suffix):
    user = User.objects.create(email=f"{suffix}-{uuid4().hex[:8]}@plane.so", username=uuid4().hex)
    user.set_password("password")
    user.save()
    return user


@pytest.mark.unit
@pytest.mark.django_db
class TestAutoAddMemberToFlaggedProjects:
    """post_save on WorkspaceMember -> enrol into that workspace's flagged projects.

    Every test here creates the joining user BEFORE any flagged project exists. Otherwise
    the User receiver auto-joins them to the workspace first and the explicit
    WorkspaceMember.objects.create() below collides with the uniqueness constraint —
    which would be testing the wrong receiver.
    """

    def test_flag_off_creates_no_project_member(self, create_user):
        joiner = make_user("flag-off")
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=False)

        WorkspaceMember.objects.create(workspace=workspace, member=joiner, role=PROJECT_MEMBER_ROLE)

        assert not ProjectMember.objects.filter(project=project, member=joiner).exists()

    def test_flag_on_creates_project_member_and_user_property(self, create_user):
        joiner = make_user("flag-on")
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=True)

        WorkspaceMember.objects.create(workspace=workspace, member=joiner, role=PROJECT_MEMBER_ROLE)

        membership = ProjectMember.objects.get(project=project, member=joiner)
        assert membership.role == PROJECT_MEMBER_ROLE
        assert membership.workspace_id == workspace.id
        # bulk_create bypasses ProjectMember.save(), so this row must be created explicitly
        assert ProjectUserProperty.objects.filter(project=project, user=joiner).exists()

    def test_guest_workspace_role_still_lands_as_project_member(self, create_user):
        """Role is always Member regardless of workspace role."""
        joiner = make_user("guest")
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=True)

        WorkspaceMember.objects.create(workspace=workspace, member=joiner, role=GUEST_ROLE)

        assert ProjectMember.objects.get(project=project, member=joiner).role == PROJECT_MEMBER_ROLE

    def test_inactive_workspace_member_is_skipped(self, create_user):
        joiner = make_user("inactive")
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=True)

        WorkspaceMember.objects.create(
            workspace=workspace, member=joiner, role=PROJECT_MEMBER_ROLE, is_active=False
        )

        assert not ProjectMember.objects.filter(project=project, member=joiner).exists()

    def test_existing_membership_is_not_duplicated_or_downgraded(self, create_user):
        joiner = make_user("existing")
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=True)
        ProjectMember.objects.create(project=project, member=joiner, role=PROJECT_ADMIN_ROLE)

        WorkspaceMember.objects.create(workspace=workspace, member=joiner, role=PROJECT_MEMBER_ROLE)

        memberships = ProjectMember.objects.filter(project=project, member=joiner)
        assert memberships.count() == 1
        assert memberships.first().role == PROJECT_ADMIN_ROLE

    def test_other_workspace_flagged_project_is_untouched(self, create_user):
        joiner = make_user("scoped")
        workspace = make_workspace(create_user)
        make_project(workspace, create_user, auto_add_new_users=True)
        other_workspace = make_workspace(create_user)
        other_project = make_project(other_workspace, create_user, auto_add_new_users=True)

        WorkspaceMember.objects.create(workspace=workspace, member=joiner, role=PROJECT_MEMBER_ROLE)

        assert not ProjectMember.objects.filter(project=other_project, member=joiner).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestAutoJoinWorkspacesForNewUser:
    """post_save on User -> join workspaces owning flagged projects, which cascades to projects."""

    def test_new_user_joins_workspace_and_project(self, create_user):
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=True)

        newcomer = make_user("newcomer")

        assert WorkspaceMember.objects.filter(workspace=workspace, member=newcomer).exists()
        assert ProjectMember.objects.get(project=project, member=newcomer).role == PROJECT_MEMBER_ROLE

    def test_new_user_ignores_unflagged_project(self, create_user):
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=False)

        newcomer = make_user("unflagged")

        assert not WorkspaceMember.objects.filter(workspace=workspace, member=newcomer).exists()
        assert not ProjectMember.objects.filter(project=project, member=newcomer).exists()

    def test_bot_user_is_skipped(self, create_user):
        workspace = make_workspace(create_user)
        project = make_project(workspace, create_user, auto_add_new_users=True)

        bot = User.objects.create(email=f"bot-{uuid4().hex[:8]}@plane.so", username=uuid4().hex, is_bot=True)

        assert not WorkspaceMember.objects.filter(workspace=workspace, member=bot).exists()
        assert not ProjectMember.objects.filter(project=project, member=bot).exists()

    def test_updating_an_existing_user_does_not_enrol(self, create_user):
        newcomer = make_user("later-flagged")
        workspace = make_workspace(create_user)
        make_project(workspace, create_user, auto_add_new_users=True)

        newcomer.first_name = "Renamed"
        newcomer.save()

        assert not WorkspaceMember.objects.filter(workspace=workspace, member=newcomer).exists()
