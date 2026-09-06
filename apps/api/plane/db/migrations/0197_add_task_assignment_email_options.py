# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0196_set_backlog_as_default_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="usernotificationpreference",
            name="task_assigned",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="project",
            name="email_on_assignment",
            field=models.BooleanField(default=False),
        ),
    ]
