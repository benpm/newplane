# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations


def set_backlog_as_default_forward(apps, schema_editor):
    State = apps.get_model("db", "State")
    Project = apps.get_model("db", "Project")

    # Unset default on all non-backlog states
    State.objects.filter(deleted_at__isnull=True).exclude(group="backlog").update(default=False)

    # Set default=True for backlog states
    State.objects.filter(deleted_at__isnull=True, group="backlog").update(default=True)

    # Update each project's default_state foreign key to its backlog state
    for project in Project.objects.filter(deleted_at__isnull=True):
        backlog = (
            State.objects.filter(project=project, group="backlog", deleted_at__isnull=True)
            .order_by("sequence")
            .first()
        )
        if backlog:
            project.default_state = backlog
            project.save(update_fields=["default_state"])


def set_backlog_as_default_backward(apps, schema_editor):
    State = apps.get_model("db", "State")
    Project = apps.get_model("db", "Project")

    # Unset default on all non-unstarted states
    State.objects.filter(deleted_at__isnull=True).exclude(group="unstarted").update(default=False)

    # Set default=True for unstarted (Todo) states
    State.objects.filter(deleted_at__isnull=True, group="unstarted").update(default=True)

    # Revert each project's default_state foreign key to its unstarted state
    for project in Project.objects.filter(deleted_at__isnull=True):
        todo = (
            State.objects.filter(project=project, group="unstarted", deleted_at__isnull=True)
            .order_by("sequence")
            .first()
        )
        if todo:
            project.default_state = todo
            project.save(update_fields=["default_state"])


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0195_discordprojectsync"),
    ]

    operations = [
        migrations.RunPython(
            set_backlog_as_default_forward,
            set_backlog_as_default_backward,
        ),
    ]
