# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Rename the "bank_wide_project" display property key to "global_project".

The key lives inside the display_properties JSON blob on every model that
stores per-user or per-view column visibility. Renaming the code without
rewriting stored rows would silently reset the column to its default for every
view an operator has already saved.

Seeded by migrations 0146 / 0148 and by plane.db.signals.project.
"""

from django.db import migrations

OLD_KEY = "bank_wide_project"
NEW_KEY = "global_project"

# (app_label, model_name) for every model carrying a display_properties JSONField.
MODELS = [
    ("db", "IssueView"),
    ("db", "ProjectUserProperty"),
    ("db", "WorkspaceUserProperties"),
    ("db", "CycleUserProperties"),
    ("db", "ModuleUserProperties"),
]


def _swap_key(apps, old_key, new_key):
    for app_label, model_name in MODELS:
        model = apps.get_model(app_label, model_name)
        rows = []
        for row in model.objects.filter(display_properties__has_key=old_key).iterator():
            props = row.display_properties or {}
            props[new_key] = props.pop(old_key)
            row.display_properties = props
            rows.append(row)
            if len(rows) >= 500:
                model.objects.bulk_update(rows, ["display_properties"])
                rows = []
        if rows:
            model.objects.bulk_update(rows, ["display_properties"])


def forward(apps, schema_editor):
    _swap_key(apps, OLD_KEY, NEW_KEY)


def backward(apps, schema_editor):
    _swap_key(apps, NEW_KEY, OLD_KEY)


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0184_rename_project_is_bank_wide_to_is_global"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
