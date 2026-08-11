# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for which assets the bulk-attach endpoint is willing to touch.

The endpoint takes a list of asset ids from the request body and re-points them
at a project. Matching them on id and workspace alone lets a member of one
project pass another project's asset ids and pull them into their own — a
cross-project hijack inside a single workspace, since workspace membership is
the only thing the caller needs.

The scoping has one deliberate hole in it: a project cover is uploaded before
the project exists, so it carries no project_id and could never match a
project-scoped filter. The uploader is therefore allowed to claim their own
unassigned covers. That exception is easy to mistake for redundancy and delete,
which would break project creation, so it is pinned here too.
"""

import pytest
from rest_framework.test import APIClient

from plane.app.permissions import ROLE
from plane.db.models import FileAsset, Page, ProjectMember, ProjectPage
from plane.tests.factories import (
    ProjectFactory,
    ProjectMemberFactory,
    UserFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
)

BULK_URL = "/api/assets/v2/workspaces/{slug}/projects/{project_id}/{entity_id}/bulk/"


def _url(slug, project_id, entity_id):
    return BULK_URL.format(slug=slug, project_id=project_id, entity_id=entity_id)


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
def project_a(workspace):
    return ProjectFactory(workspace=workspace, created_by=workspace.owner, updated_by=workspace.owner)


@pytest.fixture
def project_b(workspace):
    return ProjectFactory(workspace=workspace, created_by=workspace.owner, updated_by=workspace.owner)


@pytest.fixture
def attacker(workspace, project_a, project_b):
    """A member of project B only — deliberately not a member of project A."""
    user = UserFactory()
    WorkspaceMemberFactory(workspace=workspace, member=user, role=ROLE.MEMBER.value)
    ProjectMember.objects.update_or_create(
        project=project_b,
        member=user,
        defaults={"role": ROLE.MEMBER.value, "workspace": workspace, "is_active": True},
    )
    return user


@pytest.fixture
def page_in_b(workspace, project_b):
    """A real page to attach page images to.

    PAGE_DESCRIPTION assets are stamped with page_id=entity_id, so the entity in
    the URL has to exist or the update trips the foreign key.
    """
    page = Page(name="Target page", workspace=workspace, owned_by=workspace.owner, access=0)
    page.save(created_by_id=workspace.owner.id)
    ProjectPage.objects.create(
        workspace=workspace, project=project_b, page=page, created_by_id=workspace.owner.id
    )
    return page


def _asset(workspace, owner, *, entity_type, project=None, name="image.png"):
    asset = FileAsset(
        attributes={"name": name, "type": "image/png", "size": 100},
        asset=f"{workspace.id}/{name}",
        size=100,
        workspace=workspace,
        project=project,
        entity_type=entity_type,
        is_uploaded=True,
    )
    asset.save(created_by_id=owner.id)
    return asset


@pytest.mark.unit
@pytest.mark.django_db
class TestCrossProjectScoping:
    def test_another_projects_asset_is_not_reattached(self, workspace, project_a, project_b, attacker):
        """The whole point: project A's asset must not follow ids into project B."""
        victim = _asset(
            workspace,
            workspace.owner,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            project=project_a,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, project_b.id),
            {"asset_ids": [str(victim.id)]},
            format="json",
        )

        assert resp.status_code == 404, resp.content
        victim.refresh_from_db()
        assert victim.project_id == project_a.id

    def test_an_asset_already_in_the_project_is_accepted(
        self, workspace, project_b, attacker, page_in_b
    ):
        """Scoping must not break the ordinary case it is wrapped around."""
        own = _asset(
            workspace,
            attacker,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            project=project_b,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, page_in_b.id),
            {"asset_ids": [str(own.id)]},
            format="json",
        )
        assert resp.status_code == 204, resp.content

    def test_a_mixed_batch_only_moves_the_in_project_asset(
        self, workspace, project_a, project_b, attacker, page_in_b
    ):
        """One valid id must not smuggle a foreign one through with it."""
        own = _asset(
            workspace,
            attacker,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            project=project_b,
        )
        victim = _asset(
            workspace,
            workspace.owner,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            project=project_a,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, page_in_b.id),
            {"asset_ids": [str(own.id), str(victim.id)]},
            format="json",
        )

        assert resp.status_code == 204, resp.content
        victim.refresh_from_db()
        assert victim.project_id == project_a.id

    def test_an_asset_from_another_workspace_is_rejected(self, workspace, project_b, attacker):
        other_ws = WorkspaceFactory(owner=UserFactory())
        foreign = _asset(
            other_ws,
            other_ws.owner,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, project_b.id),
            {"asset_ids": [str(foreign.id)]},
            format="json",
        )

        assert resp.status_code == 404, resp.content
        foreign.refresh_from_db()
        assert foreign.project_id is None

    def test_no_asset_ids_is_a_bad_request(self, workspace, project_b, attacker):
        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, project_b.id), {"asset_ids": []}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.unit
@pytest.mark.django_db
class TestUnassignedProjectCoverException:
    """Covers exist before their project does, hence the carve-out."""

    def test_the_uploader_may_claim_their_own_unassigned_cover(self, workspace, project_b, attacker):
        cover = _asset(
            workspace,
            attacker,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
            project=None,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, project_b.id),
            {"asset_ids": [str(cover.id)]},
            format="json",
        )

        assert resp.status_code == 204, resp.content
        cover.refresh_from_db()
        assert cover.project_id == project_b.id
        project_b.refresh_from_db()
        assert project_b.cover_image_asset_id == cover.id

    def test_someone_elses_unassigned_cover_is_not_claimable(self, workspace, project_b, attacker):
        """The carve-out is scoped to the uploader, not to covers in general."""
        cover = _asset(
            workspace,
            workspace.owner,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
            project=None,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, project_b.id),
            {"asset_ids": [str(cover.id)]},
            format="json",
        )

        assert resp.status_code == 404, resp.content
        cover.refresh_from_db()
        assert cover.project_id is None

    def test_the_carve_out_does_not_extend_to_other_entity_types(
        self, workspace, project_b, attacker
    ):
        """Only covers are exempt; an unassigned page image stays unreachable."""
        orphan = _asset(
            workspace,
            attacker,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            project=None,
        )

        resp = _client(attacker).post(
            _url(workspace.slug, project_b.id, project_b.id),
            {"asset_ids": [str(orphan.id)]},
            format="json",
        )

        assert resp.status_code == 404, resp.content
