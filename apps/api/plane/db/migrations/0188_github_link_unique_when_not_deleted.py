# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Make the GitHub link uniqueness soft-delete aware.

Both link models used a OneToOneField, which emits a plain
``UNIQUE (page_id)`` / ``UNIQUE (issue_id)``. Plane soft-deletes, so a removed
link keeps its row and keeps occupying that constraint — meaning a page or
issue could never be re-linked once unlinked, and clearing a broken link
required a hard ``DELETE`` straight against the table.

Swapping to a ForeignKey drops the unconditional unique, and a partial unique
constraint restores "one live link per page/issue" while letting tombstones
accumulate. This mirrors the pattern already used on the same models for
``(github_sync, wiki_slug)`` and ``(github_sync, github_issue_number)``.

Written by hand rather than with makemigrations: autodetect also wanted to
sweep in a large amount of unrelated pre-existing model drift, which does not
belong in a targeted fix.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0187_workspacememberinvite_display_name"),
    ]

    operations = [
        # OneToOneField -> ForeignKey. This is what drops the unconditional
        # UNIQUE; the constraints added below take over enforcement.
        migrations.AlterField(
            model_name="githubwikipagelink",
            name="page",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="github_wiki_link",
                to="db.page",
            ),
        ),
        migrations.AlterField(
            model_name="githubissuelink",
            name="issue",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="github_link",
                to="db.issue",
            ),
        ),
        migrations.AddConstraint(
            model_name="githubwikipagelink",
            constraint=models.UniqueConstraint(
                fields=("page",),
                condition=models.Q(("deleted_at__isnull", True)),
                name="github_wiki_page_link_unique_page_when_deleted_at_null",
            ),
        ),
        migrations.AddConstraint(
            model_name="githubissuelink",
            constraint=models.UniqueConstraint(
                fields=("issue",),
                condition=models.Q(("deleted_at__isnull", True)),
                name="github_issue_link_unique_issue_when_deleted_at_null",
            ),
        ),
    ]
