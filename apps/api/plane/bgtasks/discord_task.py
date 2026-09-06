# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import requests
from celery import shared_task
from django.conf import settings

from plane.db.models import Issue, Project, State, DiscordProjectSync
from plane.utils.exception_logger import log_exception

logger = logging.getLogger(__name__)


def build_discord_embed(event_type: str, issue: Issue, changes: dict = None) -> dict:
    colors = {
        "created": 0x5865F2,   # Blurple
        "updated": 0xFEE75C,   # Yellow
        "completed": 0x57F287, # Green
    }
    action_titles = {
        "created": "New Work Item Created",
        "updated": "Work Item Updated",
        "completed": "Work Item Completed",
    }

    fields = [
        {"name": "Project", "value": issue.project.name, "inline": True},
        {"name": "State", "value": issue.state.name if issue.state else "None", "inline": True},
        {"name": "Priority", "value": (issue.priority or "None").capitalize(), "inline": True},
    ]

    if changes:
        change_lines = []
        for key, val in changes.items():
            change_lines.append(f"**{key}**: {val}")
        if change_lines:
            fields.append({"name": "Changes", "value": "\n".join(change_lines)[:1024], "inline": False})

    embed = {
        "title": f"[{issue.project.identifier}-{issue.sequence_id}] {issue.name}",
        "description": (issue.description_stripped or "")[:200],
        "color": colors.get(event_type, 0x5865F2),
        "author": {"name": action_titles.get(event_type, "Work Item Notification")},
        "fields": fields,
    }
    return embed


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_discord_notification_task(self, event_type: str, issue_id: str, changes: dict = None):
    try:
        issue = Issue.objects.select_related("project", "state", "workspace").filter(id=issue_id).first()
        if not issue:
            return

        syncs = DiscordProjectSync.objects.filter(project=issue.project, is_active=True)
        if not syncs.exists():
            return

        embed = build_discord_embed(event_type, issue, changes)
        payload = {
            "content": f"**[{issue.project.identifier}]** Work item {event_type}: **{issue.name}**",
            "embeds": [embed],
        }

        for sync in syncs:
            if event_type == "created" and not sync.notify_on_create:
                continue
            if event_type == "updated" and not sync.notify_on_update:
                continue
            if event_type == "completed" and not sync.notify_on_complete:
                continue

            if not sync.webhook_url:
                continue

            try:
                resp = requests.post(sync.webhook_url, json=payload, timeout=10)
                if not resp.ok:
                    logger.warning("Discord webhook returned status %s for sync %s", resp.status_code, sync.id)
            except Exception as exc:
                logger.error("Failed to post to Discord webhook %s: %s", sync.webhook_url, exc)
    except Exception as exc:
        log_exception(exc)


def execute_discord_command(project: Project, command_text: str, user=None) -> dict:
    """Executes a command originating from Discord or command webhook."""
    parts = command_text.strip().split()
    if not parts:
        return {"success": False, "message": "No command provided."}

    action = parts[0].lower().lstrip("/")

    if action == "help":
        return {
            "success": True,
            "message": (
                "Available commands:\n"
                "- `/create <title>` : Create a new work item\n"
                "- `/update <identifier> [title=<text>] [priority=<low|medium|high|urgent>]` : Update work item\n"
                "- `/complete <identifier>` : Mark work item as completed\n"
                "- `/status <identifier>` : View work item status"
            ),
        }

    creator = user or project.project_lead or project.workspace.owner

    if action == "create":
        if len(parts) < 2:
            return {"success": False, "message": "Usage: /create <title>"}
        title = " ".join(parts[1:])
        default_state = State.objects.filter(project=project, default=True).first() or State.objects.filter(project=project).first()
        issue = Issue.objects.create(
            name=title,
            project=project,
            workspace=project.workspace,
            state=default_state,
            created_by=creator,
        )
        send_discord_notification_task.delay("created", str(issue.id))
        return {
            "success": True,
            "message": f"Created work item [{project.identifier}-{issue.sequence_id}]: {issue.name}",
            "issue": {
                "id": str(issue.id),
                "identifier": f"{project.identifier}-{issue.sequence_id}",
                "name": issue.name,
                "state": default_state.name if default_state else None,
            },
        }

    if action in ["complete", "done"]:
        if len(parts) < 2:
            return {"success": False, "message": "Usage: /complete <identifier>"}
        identifier = parts[1].upper()
        # Find issue by sequence id or identifier string
        seq_str = identifier.split("-")[-1] if "-" in identifier else identifier
        try:
            seq_id = int(seq_str)
        except ValueError:
            return {"success": False, "message": f"Invalid identifier: {identifier}"}

        issue = Issue.objects.filter(project=project, sequence_id=seq_id).first()
        if not issue:
            return {"success": False, "message": f"Work item {identifier} not found in project."}

        completed_state = State.objects.filter(project=project, group="completed").first()
        if not completed_state:
            completed_state = State.objects.filter(project=project).last()

        old_state_name = issue.state.name if issue.state else "None"
        issue.state = completed_state
        issue.completed_at = issue.completed_at or settings.TIME_ZONE and None
        issue.save()

        send_discord_notification_task.delay("completed", str(issue.id), {"state": f"{old_state_name} -> {completed_state.name}"})
        return {
            "success": True,
            "message": f"Marked [{project.identifier}-{issue.sequence_id}] {issue.name} as completed.",
            "issue": {
                "id": str(issue.id),
                "identifier": f"{project.identifier}-{issue.sequence_id}",
                "name": issue.name,
                "state": completed_state.name if completed_state else "Completed",
            },
        }

    if action == "update":
        if len(parts) < 3:
            return {"success": False, "message": "Usage: /update <identifier> [title=<title>] [priority=<priority>]"}
        identifier = parts[1].upper()
        seq_str = identifier.split("-")[-1] if "-" in identifier else identifier
        try:
            seq_id = int(seq_str)
        except ValueError:
            return {"success": False, "message": f"Invalid identifier: {identifier}"}

        issue = Issue.objects.filter(project=project, sequence_id=seq_id).first()
        if not issue:
            return {"success": False, "message": f"Work item {identifier} not found."}

        changes = {}
        for param in parts[2:]:
            if "=" in param:
                k, v = param.split("=", 1)
                k = k.lower().strip()
                v = v.strip()
                if k in ["title", "name"]:
                    changes["name"] = f"{issue.name} -> {v}"
                    issue.name = v
                elif k == "priority" and v.lower() in ["urgent", "high", "medium", "low"]:
                    changes["priority"] = f"{issue.priority} -> {v.lower()}"
                    issue.priority = v.lower()
                elif k == "state":
                    new_st = State.objects.filter(project=project, name__iexact=v).first()
                    if new_st:
                        changes["state"] = f"{issue.state.name if issue.state else 'None'} -> {new_st.name}"
                        issue.state = new_st

        issue.save()
        send_discord_notification_task.delay("updated", str(issue.id), changes)
        return {
            "success": True,
            "message": f"Updated [{project.identifier}-{issue.sequence_id}].",
            "issue": {
                "id": str(issue.id),
                "identifier": f"{project.identifier}-{issue.sequence_id}",
                "name": issue.name,
                "state": issue.state.name if issue.state else None,
                "priority": issue.priority,
            },
        }

    if action == "status":
        if len(parts) < 2:
            return {"success": False, "message": "Usage: /status <identifier>"}
        identifier = parts[1].upper()
        seq_str = identifier.split("-")[-1] if "-" in identifier else identifier
        try:
            seq_id = int(seq_str)
        except ValueError:
            return {"success": False, "message": f"Invalid identifier: {identifier}"}

        issue = Issue.objects.filter(project=project, sequence_id=seq_id).first()
        if not issue:
            return {"success": False, "message": f"Work item {identifier} not found."}

        return {
            "success": True,
            "message": f"[{project.identifier}-{issue.sequence_id}] {issue.name} | State: {issue.state.name if issue.state else 'None'} | Priority: {issue.priority}",
            "issue": {
                "id": str(issue.id),
                "identifier": f"{project.identifier}-{issue.sequence_id}",
                "name": issue.name,
                "state": issue.state.name if issue.state else None,
                "priority": issue.priority,
            },
        }

    return {"success": False, "message": f"Unknown command '{action}'. Type /help for available commands."}
