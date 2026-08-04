# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Nested pages tree behaviour:
  list          -> roots only, with sub_pages_count annotated
  sub-pages     -> direct children only
  retrieve      -> child pages are reachable (previously 404 due to root-only queryset)
  partial_update-> re-parenting to self or a descendant is rejected (cycle guard)
  destroy       -> children re-parent to the grandparent (None for a deleted root)
"""

import pytest
from rest_framework.test import APIClient

from plane.db.models import Page, ProjectPage
from plane.tests.factories import (
    ProjectFactory,
    ProjectMemberFactory,
    UserFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
)

PAGES_URL = "/api/workspaces/{slug}/projects/{project_id}/pages/"
PAGE_URL = "/api/workspaces/{slug}/projects/{project_id}/pages/{page_id}/"
SUB_PAGES_URL = "/api/workspaces/{slug}/projects/{project_id}/pages/{page_id}/sub-pages/"


@pytest.fixture
def env(db):
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    WorkspaceMemberFactory(workspace=workspace, member=owner, role=20)
    project = ProjectFactory(workspace=workspace)
    ProjectMemberFactory(project=project, member=owner, workspace=workspace, role=20)

    client = APIClient()
    client.force_authenticate(user=owner)
    return {"owner": owner, "workspace": workspace, "project": project, "client": client}


def make_page(env, name, parent=None):
    page = Page.objects.create(
        name=name,
        workspace=env["workspace"],
        owned_by=env["owner"],
        access=0,
        parent=parent,
    )
    ProjectPage.objects.create(project=env["project"], page=page, workspace=env["workspace"])
    return page


def make_tree(env):
    """root -> child -> grandchild, plus a sibling child."""
    root = make_page(env, "root")
    child = make_page(env, "child", parent=root)
    grandchild = make_page(env, "grandchild", parent=child)
    sibling = make_page(env, "sibling", parent=root)
    return root, child, grandchild, sibling


@pytest.mark.unit
@pytest.mark.django_db
class TestNestedPagesList:
    def test_list_returns_roots_only(self, env):
        root, child, grandchild, sibling = make_tree(env)

        response = env["client"].get(PAGES_URL.format(slug=env["workspace"].slug, project_id=env["project"].id))

        assert response.status_code == 200
        ids = {str(page["id"]) for page in response.data}
        assert str(root.id) in ids
        assert str(child.id) not in ids
        assert str(grandchild.id) not in ids

    def test_list_annotates_sub_pages_count(self, env):
        root, *_ = make_tree(env)

        response = env["client"].get(PAGES_URL.format(slug=env["workspace"].slug, project_id=env["project"].id))

        root_data = next(page for page in response.data if str(page["id"]) == str(root.id))
        assert root_data["sub_pages_count"] == 2  # child + sibling, not grandchild

    def test_sub_pages_returns_direct_children_only(self, env):
        root, child, grandchild, sibling = make_tree(env)

        response = env["client"].get(
            SUB_PAGES_URL.format(slug=env["workspace"].slug, project_id=env["project"].id, page_id=root.id)
        )

        assert response.status_code == 200
        ids = {str(page["id"]) for page in response.data}
        assert ids == {str(child.id), str(sibling.id)}

    def test_child_page_is_retrievable(self, env):
        _, child, *_ = make_tree(env)

        response = env["client"].get(
            PAGE_URL.format(slug=env["workspace"].slug, project_id=env["project"].id, page_id=child.id)
        )

        assert response.status_code == 200


@pytest.mark.unit
@pytest.mark.django_db
class TestNestedPagesReparenting:
    def patch_parent(self, env, page, new_parent_id):
        return env["client"].patch(
            PAGE_URL.format(slug=env["workspace"].slug, project_id=env["project"].id, page_id=page.id),
            {"parent": str(new_parent_id)},
            format="json",
        )

    def test_reparent_to_own_descendant_is_rejected(self, env):
        root, child, grandchild, _ = make_tree(env)

        response = self.patch_parent(env, root, grandchild.id)

        assert response.status_code == 400
        root.refresh_from_db()
        assert root.parent_id is None

    def test_reparent_to_self_is_rejected(self, env):
        root, *_ = make_tree(env)

        response = self.patch_parent(env, root, root.id)

        assert response.status_code == 400

    def test_legal_reparent_succeeds(self, env):
        root, child, grandchild, sibling = make_tree(env)

        response = self.patch_parent(env, sibling, child.id)

        assert response.status_code == 200
        sibling.refresh_from_db()
        assert sibling.parent_id == child.id


@pytest.mark.unit
@pytest.mark.django_db
class TestNestedPagesDeletion:
    def delete_page(self, env, page):
        # destroy requires the page to be archived first; archive cascades to descendants
        archive = env["client"].post(
            PAGE_URL.format(slug=env["workspace"].slug, project_id=env["project"].id, page_id=page.id) + "archive/"
        )
        assert archive.status_code in (200, 204)
        return env["client"].delete(
            PAGE_URL.format(slug=env["workspace"].slug, project_id=env["project"].id, page_id=page.id)
        )

    def test_archive_cascades_to_descendants(self, env):
        root, child, grandchild, _ = make_tree(env)

        response = env["client"].post(
            PAGE_URL.format(slug=env["workspace"].slug, project_id=env["project"].id, page_id=root.id) + "archive/"
        )

        assert response.status_code in (200, 204)
        grandchild.refresh_from_db()
        assert grandchild.archived_at is not None

    def test_deleting_mid_tree_page_reparents_children_to_grandparent(self, env):
        root, child, grandchild, _ = make_tree(env)

        response = self.delete_page(env, child)

        assert response.status_code == 204
        grandchild.refresh_from_db()
        assert grandchild.parent_id == root.id

    def test_deleting_root_page_makes_children_roots(self, env):
        root, child, _, sibling = make_tree(env)

        response = self.delete_page(env, root)

        assert response.status_code == 204
        child.refresh_from_db()
        sibling.refresh_from_db()
        assert child.parent_id is None
        assert sibling.parent_id is None
