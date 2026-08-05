# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import ProjectGithubSyncSerializer
from plane.bgtasks.github_issue_sync_task import sync_github_issues_to_project
from plane.db.models import ProjectGithubSync

from ..base import BaseAPIView


def _parse_repository(repository):
    """Split an `owner/repo` string; returns (owner, name) or None."""
    if not repository or repository.count("/") != 1:
        return None
    owner, name = repository.split("/")
    owner, name = owner.strip(), name.strip()
    if not owner or not name:
        return None
    return owner, name


class ProjectGithubSyncEndpoint(BaseAPIView):
    """Manage the single GitHub repository association of a project."""

    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER], level="PROJECT")
    def get(self, request, slug, project_id):
        github_sync = ProjectGithubSync.objects.filter(workspace__slug=slug, project_id=project_id).first()
        if github_sync is None:
            return Response(None, status=status.HTTP_200_OK)
        return Response(ProjectGithubSyncSerializer(github_sync).data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        parsed = _parse_repository(request.data.get("repository", ""))
        if parsed is None:
            return Response(
                {"error": "repository must be in the form owner/repo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        owner, name = parsed

        github_sync, _ = ProjectGithubSync.objects.update_or_create(
            project_id=project_id,
            defaults={
                "repository_owner": owner,
                "repository_name": name,
                "is_issue_sync_enabled": request.data.get("is_issue_sync_enabled", True),
                "is_wiki_sync_enabled": request.data.get("is_wiki_sync_enabled", False),
            },
        )
        return Response(ProjectGithubSyncSerializer(github_sync).data, status=status.HTTP_201_CREATED)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def patch(self, request, slug, project_id):
        github_sync = ProjectGithubSync.objects.filter(workspace__slug=slug, project_id=project_id).first()
        if github_sync is None:
            return Response({"error": "No GitHub repository is connected"}, status=status.HTTP_404_NOT_FOUND)

        if "repository" in request.data:
            parsed = _parse_repository(request.data.get("repository", ""))
            if parsed is None:
                return Response(
                    {"error": "repository must be in the form owner/repo"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            github_sync.repository_owner, github_sync.repository_name = parsed

        for field in ("is_issue_sync_enabled", "is_wiki_sync_enabled"):
            if field in request.data:
                setattr(github_sync, field, bool(request.data.get(field)))

        github_sync.save()
        return Response(ProjectGithubSyncSerializer(github_sync).data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def delete(self, request, slug, project_id):
        github_sync = ProjectGithubSync.objects.filter(workspace__slug=slug, project_id=project_id).first()
        if github_sync is not None:
            github_sync.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectGithubSyncNowEndpoint(BaseAPIView):
    """Manually trigger an issue sync run."""

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        github_sync = ProjectGithubSync.objects.filter(workspace__slug=slug, project_id=project_id).first()
        if github_sync is None:
            return Response({"error": "No GitHub repository is connected"}, status=status.HTTP_404_NOT_FOUND)

        sync_github_issues_to_project.delay(str(github_sync.id))
        return Response({"message": "Sync started"}, status=status.HTTP_202_ACCEPTED)
