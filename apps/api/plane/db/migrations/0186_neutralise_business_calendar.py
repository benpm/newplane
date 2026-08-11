# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Neutralise the seeded Vietnam Banking calendar.

Migration 0167 seeded a "Vietnam Banking" default WorkSchedule with MOLISA
public holidays and swap-day overrides. De-branding the fork drops that
regional data: the calendar feature stays, but ships with an empty, neutral
default schedule that operators populate through God Mode.

The data step is one-way: the holiday rows are regional data, not derived
state. Rolling back leaves the schedule renamed and empty rather than
re-inventing dates that now belong to whatever calendar the operator runs.
"""

from django.db import migrations, models

DEFAULT_SCHEDULE_ID = "00000000-0000-0000-0000-000000000001"


def neutralise(apps, schema_editor):
    WorkSchedule = apps.get_model("db", "WorkSchedule")
    Holiday = apps.get_model("db", "Holiday")
    DayOverride = apps.get_model("db", "DayOverride")

    schedule = WorkSchedule.objects.filter(id=DEFAULT_SCHEDULE_ID).first()
    if schedule is None:
        return

    # Only rows attached to the seeded default schedule are removed. Anything an
    # operator added against a schedule of their own is left untouched.
    Holiday.objects.filter(schedule=schedule).delete()
    DayOverride.objects.filter(schedule=schedule).delete()

    schedule.name = "Default Schedule"
    schedule.timezone = "UTC"
    schedule.country_code = ""
    schedule.save(update_fields=["name", "timezone", "country_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0185_rename_bank_wide_display_property"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workschedule",
            name="timezone",
            field=models.CharField(default="UTC", max_length=64),
        ),
        migrations.AlterField(
            model_name="workschedule",
            name="country_code",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
        migrations.RunPython(neutralise, migrations.RunPython.noop),
    ]
