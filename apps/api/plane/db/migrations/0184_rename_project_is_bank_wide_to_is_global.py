# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Rename Project.is_bank_wide to Project.is_global.

Part of de-branding the fork: the "Bank-wide Projects" feature is unchanged in
behaviour, only in name ("Global Projects").
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0183_delete_help_center"),
    ]

    operations = [
        migrations.RenameField(
            model_name="project",
            old_name="is_bank_wide",
            new_name="is_global",
        ),
        migrations.AlterField(
            model_name="project",
            name="is_global",
            field=models.BooleanField(default=False, verbose_name="Is Global Project"),
        ),
    ]
