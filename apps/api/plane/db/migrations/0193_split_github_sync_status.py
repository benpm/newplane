# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Give the issue sync and the wiki sync their own status fields.

Both syncs wrote `last_sync_status`/`last_synced_at`, and both run from the same
five-minute beat. The wiki task is much slower -- it clones a repo, converts every
page and pushes -- so it reliably finished last and erased whatever the issue sync
had just recorded. On the live instance the column read "wiki success: 0 pulled,
0 pushed, 0 pages, 0 files" while the issue sync had completed successfully 0.8s
earlier, which is exactly what that race predicts.

The cost was not cosmetic: an issue-sync failure was undetectable from the UI. That
is tolerable for a read-only poll and not tolerable for a sync that is about to
start creating and editing issues on GitHub.

Existing values are split by their prefix, since the wiki task tagged its own
strings with "wiki ". That prefix is now redundant -- the field carries the sync
type -- so it is dropped on the way across.

`issues_synced_at` is renamed to `issues_cursor_at` at the same time. It is a
position in GitHub's change stream passed as the `since` parameter, not a record
of when a run finished, and leaving it one character away from the new
`issue_synced_at` invites exactly the mix-up that would corrupt the cursor or
surface it to the UI as a sync time.
"""

from django.db import migrations, models


def split_status(apps, schema_editor):
    ProjectGithubSync = apps.get_model("db", "ProjectGithubSync")
    for row in ProjectGithubSync.objects.exclude(last_sync_status__isnull=True).iterator():
        status = row.last_sync_status or ""
        if not status:
            continue
        if status.startswith("wiki "):
            row.wiki_sync_status = status[len("wiki ") :][:255]
            row.wiki_synced_at = row.last_synced_at
        else:
            row.issue_sync_status = status[:255]
            row.issue_synced_at = row.last_synced_at
        row.save(
            update_fields=[
                "issue_sync_status",
                "issue_synced_at",
                "wiki_sync_status",
                "wiki_synced_at",
            ]
        )


def merge_status(apps, schema_editor):
    """Collapse back to one pair, keeping whichever sync reported most recently."""
    ProjectGithubSync = apps.get_model("db", "ProjectGithubSync")
    for row in ProjectGithubSync.objects.all().iterator():
        issue_at, wiki_at = row.issue_synced_at, row.wiki_synced_at
        if wiki_at and (issue_at is None or wiki_at >= issue_at):
            row.last_sync_status = (f"wiki {row.wiki_sync_status}" if row.wiki_sync_status else None)
            row.last_synced_at = wiki_at
        elif issue_at:
            row.last_sync_status = row.issue_sync_status
            row.last_synced_at = issue_at
        else:
            continue
        row.save(update_fields=["last_sync_status", "last_synced_at"])


class Migration(migrations.Migration):
    dependencies = [("db", "0192_workspaceinvitelink")]

    operations = [
        migrations.AddField(
            model_name="projectgithubsync",
            name="issue_sync_status",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="projectgithubsync",
            name="issue_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectgithubsync",
            name="wiki_sync_status",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="projectgithubsync",
            name="wiki_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(split_status, merge_status),
        migrations.RemoveField(model_name="projectgithubsync", name="last_sync_status"),
        migrations.RemoveField(model_name="projectgithubsync", name="last_synced_at"),
        migrations.RenameField(
            model_name="projectgithubsync",
            old_name="issues_synced_at",
            new_name="issues_cursor_at",
        ),
    ]
