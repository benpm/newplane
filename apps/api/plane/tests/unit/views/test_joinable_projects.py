# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status
from django.urls import reverse

from plane.db.models import Project, ProjectMember, WorkspaceMember, User
from plane.db.models.project import ProjectNetwork, ROLE


@pytest.mark.unit
class TestJoinableProjects:
    @pytest.mark.django_db
    def test_unauthenticated_cannot_access_joinable_projects(self, api_client):
        url = reverse("user-joinable-projects")
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.django_db
    def test_list_and_join_joinable_project(self, session_client, workspace):
        project = Project.objects.create(
            name="Open Public Project",
            identifier="OPP",
            network=ProjectNetwork.PUBLIC.value,
            workspace=workspace,
        )

        new_user = User.objects.create_user(email="newuser@example.com", username="newuser")
        session_client.force_authenticate(user=new_user)

        # List joinable projects
        url = reverse("user-joinable-projects")
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        opp = next((p for p in data if p["id"] == str(project.id)), None)
        assert opp is not None
        assert opp["name"] == "Open Public Project"
        assert opp["is_member"] is False

        # Join project
        join_url = reverse("user-join-project", kwargs={"project_id": project.id})
        join_resp = session_client.post(join_url, {}, format="json")
        assert join_resp.status_code == status.HTTP_200_OK
        assert join_resp.json()["workspace_slug"] == workspace.slug

        # Verify memberships
        assert WorkspaceMember.objects.filter(workspace=workspace, member=new_user, is_active=True).exists()
        assert ProjectMember.objects.filter(project=project, member=new_user, is_active=True, role=ROLE.MEMBER.value).exists()

    @pytest.mark.django_db
    def test_normal_user_cannot_create_project(self, session_client, workspace):
        normal_user = User.objects.create_user(email="normal@example.com", username="normal")
        WorkspaceMember.objects.create(workspace=workspace, member=normal_user, role=ROLE.MEMBER.value)

        session_client.force_authenticate(user=normal_user)
        url = f"/api/workspaces/{workspace.slug}/projects/"
        response = session_client.post(url, {"name": "Unauthorized Project", "identifier": "UNAUTH"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
