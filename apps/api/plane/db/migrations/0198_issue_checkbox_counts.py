# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models
from plane.utils.checkbox import extract_checkbox_counts


def populate_checkbox_counts(apps, schema_editor):
    Issue = apps.get_model("db", "Issue")
    for issue in Issue._default_manager.exclude(description_html__isnull=True).exclude(description_html="").exclude(description_html="<p></p>").iterator(chunk_size=1000):
        total, completed = extract_checkbox_counts(issue.description_html)
        if total > 0:
            Issue._default_manager.filter(pk=issue.pk).update(
                checkbox_total=total, checkbox_completed=completed
            )


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0197_add_task_assignment_email_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="checkbox_total",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="issue",
            name="checkbox_completed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(populate_checkbox_counts, reverse_code=migrations.RunPython.noop),
    ]
