# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Let a link record what content it last carried, and how much discussion sits on GitHub.

Syncing title and description both ways needs a way to tell "this side changed"
from "this side was merely saved". A timestamp cannot answer that: Issue.updated_at
moves on any full save, so a priority or assignee change looks exactly like a
description edit, and acting on it would push stale text over a real GitHub edit.

So the link stores a hash of the content it last transferred. The hash answers
whether a side changed; the timestamp beside it only gates the comparison and
breaks ties when both sides changed. Both are null for every existing link, which
reads as "never transferred" and makes the first run treat GitHub as the source of
truth -- the right default, since GitHub is where all current content came from.

github_comment_count is mirrored from the same payload the sync already fetches;
the issues API returns it for free. Comments are deliberately not synced, so this
exists to show that discussion is happening somewhere the work item cannot show it.
Zero is correct for existing rows: the next run overwrites it with the real count.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0193_split_github_sync_status")]

    operations = [
        migrations.AddField(
            model_name="githubissuelink",
            name="content_hash",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="githubissuelink",
            name="content_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="githubissuelink",
            name="github_comment_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
