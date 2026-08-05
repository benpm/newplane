# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the nested page tree.

Pages are one of the features this instance actually uses, and the tree is
recent fork code, so it carries more risk than its line count suggests. The
invariants worth pinning are the ones a user would notice: the expander count
must agree with what expanding actually returns, moving a page must not be able
to create a loop, and deleting a parent must not strand its children.
"""

import pytest
from rest_framework.test import APIClient

from plane.app.permissions import ROLE
from plane.db.models import Page, ProjectMember, ProjectPage
from plane.tests.factories import (
    ProjectFactory,
    ProjectMemberFactory,
    UserFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
)

PAGES_URL = "/api/workspaces/{slug}/projects/{project_id}/pages/"


def _url(slug, project_id, suffix=""):
    return PAGES_URL.format(slug=slug, project_id=project_id) + suffix


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


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
def member(workspace, project):
    user = UserFactory()
    WorkspaceMemberFactory(workspace=workspace, member=user, role=ROLE.MEMBER.value)
    ProjectMemberFactory(project=project, member=user, role=ROLE.MEMBER.value)
    return user


@pytest.fixture
def other_member(workspace, project):
    user = UserFactory()
    WorkspaceMemberFactory(workspace=workspace, member=user, role=ROLE.MEMBER.value)
    ProjectMemberFactory(project=project, member=user, role=ROLE.MEMBER.value)
    return user


def _project_admin(workspace, project):
    """A workspace admin holding project admin.

    Granting workspace admin already enrols the user in every project, so the
    project membership has to be updated rather than created a second time.
    """
    user = UserFactory()
    WorkspaceMemberFactory(workspace=workspace, member=user, role=ROLE.ADMIN.value)
    ProjectMember.objects.update_or_create(
        project=project,
        member=user,
        defaults={"role": ROLE.ADMIN.value, "workspace": workspace, "is_active": True},
    )
    return user


def _make_page(project, workspace, owner, *, name="Page", parent=None, access=0):
    """Create a page linked to the project, bypassing the API."""
    page = Page(name=name, workspace=workspace, owned_by=owner, access=access, parent=parent)
    page.save(created_by_id=owner.id)
    ProjectPage.objects.create(
        workspace=workspace, project=project, page=page, created_by_id=owner.id
    )
    return page


@pytest.mark.unit
@pytest.mark.django_db
class TestSubPageCountMatchesVisibility:
    """The expander count must agree with what expanding returns."""

    def test_public_children_are_counted(self, member, workspace, project):
        parent = _make_page(project, workspace, member, name="Parent")
        _make_page(project, workspace, member, name="Child", parent=parent, access=0)

        listed = _client(member).get(_url(workspace.slug, project.id)).json()
        row = next(p for p in listed if p["id"] == str(parent.id))
        assert row["sub_pages_count"] == 1

    def test_private_child_of_another_user_is_not_counted(
        self, member, other_member, workspace, project
    ):
        """Counting it would advertise an expander that opens onto nothing."""
        parent = _make_page(project, workspace, member, name="Parent")
        _make_page(
            project, workspace, other_member, name="Their private child", parent=parent, access=1
        )

        client = _client(member)
        listed = client.get(_url(workspace.slug, project.id)).json()
        row = next(p for p in listed if p["id"] == str(parent.id))

        sub_pages = client.get(_url(workspace.slug, project.id, f"{parent.id}/sub-pages/")).json()
        assert row["sub_pages_count"] == len(sub_pages) == 0

    def test_own_private_child_is_counted_and_returned(self, member, workspace, project):
        parent = _make_page(project, workspace, member, name="Parent")
        _make_page(project, workspace, member, name="My private child", parent=parent, access=1)

        client = _client(member)
        listed = client.get(_url(workspace.slug, project.id)).json()
        row = next(p for p in listed if p["id"] == str(parent.id))
        sub_pages = client.get(_url(workspace.slug, project.id, f"{parent.id}/sub-pages/")).json()

        assert row["sub_pages_count"] == len(sub_pages) == 1

    def test_soft_deleted_children_are_not_counted(self, member, workspace, project):
        parent = _make_page(project, workspace, member, name="Parent")
        child = _make_page(project, workspace, member, name="Child", parent=parent)
        child.delete()  # soft delete

        listed = _client(member).get(_url(workspace.slug, project.id)).json()
        row = next(p for p in listed if p["id"] == str(parent.id))
        assert row["sub_pages_count"] == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestListReturnsRootsOnly:
    def test_children_are_not_listed_at_the_top_level(self, member, workspace, project):
        parent = _make_page(project, workspace, member, name="Parent")
        child = _make_page(project, workspace, member, name="Child", parent=parent)

        listed = _client(member).get(_url(workspace.slug, project.id)).json()
        ids = {p["id"] for p in listed}
        assert str(parent.id) in ids
        assert str(child.id) not in ids


@pytest.mark.unit
@pytest.mark.django_db
class TestReparentingRejectsCycles:
    def test_a_page_cannot_become_its_own_parent(self, member, workspace, project):
        page = _make_page(project, workspace, member, name="Page")
        resp = _client(member).patch(
            _url(workspace.slug, project.id, f"{page.id}/"), {"parent": str(page.id)}, format="json"
        )
        assert resp.status_code == 400

    def test_a_page_cannot_move_under_its_own_descendant(self, member, workspace, project):
        grandparent = _make_page(project, workspace, member, name="Grandparent")
        parent = _make_page(project, workspace, member, name="Parent", parent=grandparent)
        child = _make_page(project, workspace, member, name="Child", parent=parent)

        resp = _client(member).patch(
            _url(workspace.slug, project.id, f"{grandparent.id}/"),
            {"parent": str(child.id)},
            format="json",
        )
        assert resp.status_code == 400
        grandparent.refresh_from_db()
        assert grandparent.parent_id is None

    def test_moving_under_an_unrelated_page_is_allowed(self, member, workspace, project):
        page = _make_page(project, workspace, member, name="Page")
        target = _make_page(project, workspace, member, name="Target")

        resp = _client(member).patch(
            _url(workspace.slug, project.id, f"{page.id}/"),
            {"parent": str(target.id)},
            format="json",
        )
        assert resp.status_code in (200, 204), resp.content
        page.refresh_from_db()
        assert page.parent_id == target.id


@pytest.mark.unit
@pytest.mark.django_db
class TestDeleteKeepsChildrenReachable:
    def test_children_are_promoted_to_the_deleted_pages_parent(self, workspace, project):
        """Otherwise the subtree would be orphaned under a missing parent."""
        admin = _project_admin(workspace, project)

        grandparent = _make_page(project, workspace, admin, name="Grandparent")
        parent = _make_page(project, workspace, admin, name="Parent", parent=grandparent)
        child = _make_page(project, workspace, admin, name="Child", parent=parent)

        client = _client(admin)
        # Deletion is only allowed once archived, and archiving cascades to the
        # descendants, so the child is archived by the time the parent goes.
        assert client.post(_url(workspace.slug, project.id, f"{parent.id}/archive/")).status_code == 200
        resp = client.delete(_url(workspace.slug, project.id, f"{parent.id}/"))
        assert resp.status_code == 204, resp.content

        child.refresh_from_db()
        assert child.parent_id == grandparent.id

    def test_children_of_a_deleted_root_become_roots(self, workspace, project):
        admin = _project_admin(workspace, project)

        root = _make_page(project, workspace, admin, name="Root")
        child = _make_page(project, workspace, admin, name="Child", parent=root)

        client = _client(admin)
        assert client.post(_url(workspace.slug, project.id, f"{root.id}/archive/")).status_code == 200
        assert client.delete(_url(workspace.slug, project.id, f"{root.id}/")).status_code == 204
        child.refresh_from_db()
        assert child.parent_id is None


@pytest.mark.unit
@pytest.mark.django_db
class TestArchiveCascade:
    def test_archiving_a_parent_archives_its_descendants(self, workspace, project):
        admin = _project_admin(workspace, project)
        root = _make_page(project, workspace, admin, name="Root")
        child = _make_page(project, workspace, admin, name="Child", parent=root)
        grandchild = _make_page(project, workspace, admin, name="Grandchild", parent=child)

        resp = _client(admin).post(_url(workspace.slug, project.id, f"{root.id}/archive/"))
        assert resp.status_code == 200, resp.content

        for page in (root, child, grandchild):
            page.refresh_from_db()
            assert page.archived_at is not None

    def test_a_parent_loop_does_not_hang_the_archive(self, workspace, project):
        """A pre-existing cycle must terminate rather than spin until timeout.

        Re-parenting rejects new cycles, but the recursive walk must not depend
        on that guard having existed for every row ever written, so the loop is
        forced directly on the rows here.
        """
        admin = _project_admin(workspace, project)
        first = _make_page(project, workspace, admin, name="First")
        second = _make_page(project, workspace, admin, name="Second", parent=first)
        Page.objects.filter(pk=first.pk).update(parent=second)

        resp = _client(admin).post(_url(workspace.slug, project.id, f"{first.id}/archive/"))
        assert resp.status_code == 200, resp.content

        for page in (first, second):
            page.refresh_from_db()
            assert page.archived_at is not None
