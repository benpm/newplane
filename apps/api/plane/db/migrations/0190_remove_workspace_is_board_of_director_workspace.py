# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Drop ``workspaces.is_board_of_director_workspace``.

Added in 0138 to gate the HO ("Overall Management") and Bank-wide Projects
sidebar entries to a single board-of-director workspace. Commit 4cf1f8092c
deleted both guards from the CE ``SidebarItem``, leaving a checkbox in workspace
settings that wrote a column nothing read. The nav items are unconditional now,
so the column goes with the check.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0189_sync_model_state'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='workspace',
            name='is_board_of_director_workspace',
        ),
    ]
