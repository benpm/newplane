# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.bgtasks.discord_task import execute_discord_command
from plane.db.models import DiscordProjectSync, Project


class ProjectDiscordIntegrationViewSet(BaseViewSet):
    model = DiscordProjectSync

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="PROJECT")
    def list(self, request, slug, project_id):
        integrations = DiscordProjectSync.objects.filter(
            project_id=project_id,
            workspace__slug=slug,
        ).order_by("-created_at")

        data = [
            {
                "id": str(item.id),
                "server_id": item.server_id,
                "server_name": item.server_name,
                "channel_id": item.channel_id,
                "webhook_url": item.webhook_url,
                "notify_on_create": item.notify_on_create,
                "notify_on_update": item.notify_on_update,
                "notify_on_complete": item.notify_on_complete,
                "is_active": item.is_active,
                "created_at": item.created_at,
            }
            for item in integrations
        ]
        return Response(data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="PROJECT")
    def create(self, request, slug, project_id):
        project = Project.objects.filter(id=project_id, workspace__slug=slug).first()
        if not project:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        server_id = request.data.get("server_id")
        webhook_url = request.data.get("webhook_url")
        if not server_id or not webhook_url:
            return Response(
                {"error": "server_id and webhook_url are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        integration = DiscordProjectSync.objects.create(
            project=project,
            workspace=project.workspace,
            server_id=server_id,
            server_name=request.data.get("server_name", f"Server {server_id}"),
            channel_id=request.data.get("channel_id", ""),
            webhook_url=webhook_url,
            bot_token=request.data.get("bot_token", ""),
            notify_on_create=request.data.get("notify_on_create", True),
            notify_on_update=request.data.get("notify_on_update", True),
            notify_on_complete=request.data.get("notify_on_complete", True),
            is_active=request.data.get("is_active", True),
            created_by=request.user,
        )

        return Response(
            {
                "id": str(integration.id),
                "server_id": integration.server_id,
                "server_name": integration.server_name,
                "webhook_url": integration.webhook_url,
                "notify_on_create": integration.notify_on_create,
                "notify_on_update": integration.notify_on_update,
                "notify_on_complete": integration.notify_on_complete,
                "is_active": integration.is_active,
            },
            status=status.HTTP_201_CREATED,
        )

    @allow_permission([ROLE.ADMIN], level="PROJECT")
    def partial_update(self, request, slug, project_id, pk):
        integration = DiscordProjectSync.objects.filter(
            id=pk,
            project_id=project_id,
            workspace__slug=slug,
        ).first()
        if not integration:
            return Response({"error": "Integration not found"}, status=status.HTTP_404_NOT_FOUND)

        updatable_fields = [
            "server_name",
            "channel_id",
            "webhook_url",
            "bot_token",
            "notify_on_create",
            "notify_on_update",
            "notify_on_complete",
            "is_active",
        ]
        for field in updatable_fields:
            if field in request.data:
                setattr(integration, field, request.data[field])

        integration.save()
        return Response(
            {
                "id": str(integration.id),
                "server_id": integration.server_id,
                "server_name": integration.server_name,
                "webhook_url": integration.webhook_url,
                "notify_on_create": integration.notify_on_create,
                "notify_on_update": integration.notify_on_update,
                "notify_on_complete": integration.notify_on_complete,
                "is_active": integration.is_active,
            },
            status=status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN], level="PROJECT")
    def destroy(self, request, slug, project_id, pk):
        integration = DiscordProjectSync.objects.filter(
            id=pk,
            project_id=project_id,
            workspace__slug=slug,
        ).first()
        if not integration:
            return Response({"error": "Integration not found"}, status=status.HTTP_404_NOT_FOUND)

        integration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectDiscordCommandEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="PROJECT")
    def post(self, request, slug, project_id):
        project = Project.objects.filter(id=project_id, workspace__slug=slug).select_related("workspace").first()
        if not project:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        command = request.data.get("command", "")
        if not command:
            return Response({"error": "command is required"}, status=status.HTTP_400_BAD_REQUEST)

        result = execute_discord_command(project, command, user=request.user)
        return Response(result, status=status.HTTP_200_OK if result.get("success") else status.HTTP_400_BAD_REQUEST)
