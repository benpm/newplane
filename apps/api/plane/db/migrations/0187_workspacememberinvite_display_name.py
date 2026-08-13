# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Carry an intended display name on a workspace invite.

Invites are addressed by email, and a new account derives its display name
from the local part of that address ("j.smith" from j.smith@example.com).
Naming the person at invite time lets the account arrive correctly labelled
instead of needing a rename afterwards.

Blank is the norm: every invite created before this migration, and every
invite made through the stock workspace-settings UI, has no name attached.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0186_neutralise_business_calendar"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspacememberinvite",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
