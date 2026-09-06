# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Project, Issue, Page, State, WorkspaceMember
from plane.db.models.project import ProjectNetwork, ROLE


@pytest.mark.unit
class TestGuestPublicAccess:
    @pytest.mark.django_db
    def test_unauthenticated_can_view_tasks_of_public_project(self, api_client, workspace):
        project = Project.objects.create(
            name="Public Guest Project",
            identifier="PGP",
            network=ProjectNetwork.PUBLIC.value,
            workspace=workspace,
        )
        state = State.objects.create(
            name="Todo",
            group="unstarted",
            project=project,
            workspace=workspace,
        )
        issue = Issue.objects.create(
            name="Public Task",
            project=project,
            workspace=workspace,
            state=state,
        )

        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        detail_url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/"
        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_unauthenticated_cannot_create_or_modify_task(self, api_client, workspace):
        project = Project.objects.create(
            name="Public Guest Project",
            identifier="PGP",
            network=ProjectNetwork.PUBLIC.value,
            workspace=workspace,
        )
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/"
        response = api_client.post(url, {"name": "Unauthorized Task"}, format="json")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.django_db
    def test_unauthenticated_can_view_public_pages(self, api_client, workspace):
        project = Project.objects.create(
            name="Public Guest Project",
            identifier="PGP",
            network=ProjectNetwork.PUBLIC.value,
            workspace=workspace,
        )
        page = Page.objects.create(
            name="Public Page",
            access=Page.PUBLIC_ACCESS,
            workspace=workspace,
            owned_by=workspace.owner,
        )
        page.projects.add(project, through_defaults={"workspace": workspace})

        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_unauthenticated_cannot_create_pages(self, api_client, workspace):
        project = Project.objects.create(
            name="Public Guest Project",
            identifier="PGP",
            network=ProjectNetwork.PUBLIC.value,
            workspace=workspace,
        )
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"
        response = api_client.post(url, {"name": "Unauthorized Page"}, format="json")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
