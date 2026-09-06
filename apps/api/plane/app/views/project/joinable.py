# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.db.models import Project, ProjectMember, ProjectUserProperty, WorkspaceMember
from plane.db.models.project import ProjectNetwork, ROLE


class JoinableProjectsEndpoint(BaseAPIView):
    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        projects = (
            Project.objects.filter(
                network=ProjectNetwork.PUBLIC.value,
                archived_at__isnull=True,
            )
            .select_related("workspace")
            .order_by("workspace__name", "name")
        )

        data = []
        for project in projects:
            is_member = ProjectMember.objects.filter(
                project=project,
                member=request.user,
                is_active=True,
            ).exists()
            data.append(
                {
                    "id": str(project.id),
                    "name": project.name,
                    "identifier": project.identifier,
                    "description": project.description or "",
                    "emoji": project.emoji or "",
                    "icon_prop": project.icon_prop,
                    "is_member": is_member,
                    "workspace": {
                        "id": str(project.workspace.id),
                        "name": project.workspace.name,
                        "slug": project.workspace.slug,
                        "logo_url": project.workspace.logo_url or "",
                    },
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class JoinProjectEndpoint(BaseAPIView):
    def post(self, request, project_id):
        if not request.user or not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        project = (
            Project.objects.filter(
                id=project_id,
                network=ProjectNetwork.PUBLIC.value,
                archived_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )

        if not project:
            return Response({"error": "Project not found or not joinable"}, status=status.HTTP_404_NOT_FOUND)

        workspace = project.workspace

        workspace_member, _ = WorkspaceMember.objects.get_or_create(
            workspace=workspace,
            member=request.user,
            defaults={"role": ROLE.MEMBER.value, "is_active": True},
        )
        if not workspace_member.is_active:
            workspace_member.is_active = True
            workspace_member.save(update_fields=["is_active"])

        project_member, _ = ProjectMember.objects.get_or_create(
            workspace=workspace,
            project=project,
            member=request.user,
            defaults={"role": ROLE.MEMBER.value, "is_active": True},
        )
        if not project_member.is_active:
            project_member.is_active = True
            project_member.save(update_fields=["is_active"])

        ProjectUserProperty.objects.get_or_create(
            project=project,
            user=request.user,
            workspace=workspace,
            defaults={"created_by": request.user},
        )

        user_profile = getattr(request.user, "profile", None)
        if user_profile:
            user_profile.last_workspace_id = workspace.id
            if isinstance(user_profile.onboarding_step, dict):
                user_profile.onboarding_step["workspace_join"] = True
                user_profile.onboarding_step["workspace_create"] = True
            user_profile.is_onboarded = True
            user_profile.save()

        return Response(
            {
                "message": "Successfully joined project",
                "workspace_slug": workspace.slug,
                "project_id": str(project.id),
                "project_identifier": project.identifier,
            },
            status=status.HTTP_200_OK,
        )
