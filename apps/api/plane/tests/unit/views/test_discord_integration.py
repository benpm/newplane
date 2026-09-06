# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch
import pytest
from rest_framework import status

from plane.db.models import Project, Issue, State, DiscordProjectSync, WorkspaceMember
from plane.bgtasks.discord_task import (
    build_discord_embed,
    execute_discord_command,
    send_discord_notification_task,
)
from plane.db.models.project import ProjectNetwork, ROLE


@pytest.mark.unit
class TestDiscordIntegration:
    @pytest.mark.django_db
    def test_multiple_discord_servers_for_same_project(self, session_client, workspace):
        project = Project.objects.create(
            name="Discord Project",
            identifier="DISC",
            network=ProjectNetwork.PUBLIC.value,
            workspace=workspace,
        )

        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/discord/"

        # Add Server 1
        resp1 = session_client.post(
            url,
            {
                "server_id": "guild_111",
                "server_name": "Dev Team Discord",
                "webhook_url": "https://discord.com/api/webhooks/111/token1",
                "notify_on_create": True,
                "notify_on_update": False,
                "notify_on_complete": True,
            },
            format="json",
        )
        assert resp1.status_code == status.HTTP_201_CREATED

        # Add Server 2 (same project, different server)
        resp2 = session_client.post(
            url,
            {
                "server_id": "guild_222",
                "server_name": "Community Discord",
                "webhook_url": "https://discord.com/api/webhooks/222/token2",
                "notify_on_create": True,
                "notify_on_update": True,
                "notify_on_complete": True,
            },
            format="json",
        )
        assert resp2.status_code == status.HTTP_201_CREATED

        # Verify multiple integrations exist for the project
        list_resp = session_client.get(url)
        assert list_resp.status_code == status.HTTP_200_OK
        data = list_resp.json()
        assert len(data) == 2
        server_ids = {s["server_id"] for s in data}
        assert "guild_111" in server_ids
        assert "guild_222" in server_ids

    @pytest.mark.django_db
    def test_customizable_notification_settings(self, session_client, workspace):
        project = Project.objects.create(
            name="Discord Custom Project",
            identifier="CUST",
            workspace=workspace,
        )
        sync = DiscordProjectSync.objects.create(
            project=project,
            workspace=workspace,
            server_id="guild_333",
            server_name="Custom Server",
            webhook_url="https://discord.com/api/webhooks/333/token",
            notify_on_create=True,
            notify_on_update=True,
            notify_on_complete=True,
        )

        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/discord/{sync.id}/"
        patch_resp = session_client.patch(
            url,
            {"notify_on_update": False, "notify_on_create": False},
            format="json",
        )
        assert patch_resp.status_code == status.HTTP_200_OK
        assert patch_resp.json()["notify_on_update"] is False
        assert patch_resp.json()["notify_on_create"] is False

    @pytest.mark.django_db
    def test_discord_commands(self, session_client, workspace):
        project = Project.objects.create(
            name="Command Project",
            identifier="CMD",
            workspace=workspace,
        )
        State.objects.create(
            name="Todo", group="unstarted", project=project, workspace=workspace, default=True
        )
        state_done = State.objects.create(
            name="Done", group="completed", project=project, workspace=workspace
        )

        command_url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/discord/command/"

        # Test /help
        help_resp = session_client.post(command_url, {"command": "/help"}, format="json")
        assert help_resp.status_code == status.HTTP_200_OK
        assert "Available commands" in help_resp.json()["message"]

        # Test /create command
        create_resp = session_client.post(command_url, {"command": "/create Implement Discord bot commands"}, format="json")
        assert create_resp.status_code == status.HTTP_200_OK
        assert create_resp.json()["success"] is True
        created_issue = Issue.objects.filter(project=project, name="Implement Discord bot commands").first()
        assert created_issue is not None
        assert created_issue.sequence_id is not None

        # Test /status command
        status_resp = session_client.post(command_url, {"command": f"/status {project.identifier}-{created_issue.sequence_id}"}, format="json")
        assert status_resp.status_code == status.HTTP_200_OK
        assert status_resp.json()["success"] is True
        assert "Implement Discord bot commands" in status_resp.json()["message"]

        # Test /update command
        update_resp = session_client.post(
            command_url,
            {"command": f"/update {created_issue.sequence_id} priority=urgent"},
            format="json",
        )
        assert update_resp.status_code == status.HTTP_200_OK
        created_issue.refresh_from_db()
        assert created_issue.priority == "urgent"

        # Test /complete command
        complete_resp = session_client.post(
            command_url,
            {"command": f"/complete {created_issue.sequence_id}"},
            format="json",
        )
        assert complete_resp.status_code == status.HTTP_200_OK
        created_issue.refresh_from_db()
        assert created_issue.state == state_done

    @pytest.mark.django_db
    @patch("requests.post")
    def test_discord_notification_dispatch(self, mock_post, workspace):
        project = Project.objects.create(name="Notify Project", identifier="NOTIF", workspace=workspace)
        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        issue = Issue.objects.create(name="Discord Alert Test", project=project, workspace=workspace, state=state)

        DiscordProjectSync.objects.create(
            project=project,
            workspace=workspace,
            server_id="guild_notify",
            webhook_url="https://discord.com/api/webhooks/notify/hook",
            notify_on_create=True,
            notify_on_update=True,
            notify_on_complete=True,
        )

        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 200

        # Trigger notification task
        send_discord_notification_task("created", str(issue.id))
        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://discord.com/api/webhooks/notify/hook"
        payload = call_args[1]["json"]
        assert "Discord Alert Test" in payload["content"]
        assert len(payload["embeds"]) == 1
        assert "New Work Item Created" in payload["embeds"][0]["author"]["name"]
